"""Agent 评测报告生成器。

这个模块把同一批固定 eval cases 同时跑在手写 pipeline 和 LangGraph shadow 上，
用表格检查两条路径的意图、工具、停止原因和 RAG 命中是否一致。
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from clothing_rag_demo.agent.agent_executor import run_agent
from clothing_rag_demo.agent.eval_cases import EVAL_CASES
from clothing_rag_demo.agent.langgraph_executor import run_langgraph_agent
from clothing_rag_demo.agent.tool_registry import build_default_tool_registry


DEFAULT_EXECUTORS = {
    "pipeline": run_agent,
    "langgraph": run_langgraph_agent,
}


# fake tools 让评测只关注调度行为，不被真实向量库、真实模型或网络状态影响。
def fake_rag_runner(query, query_type=None):
    return {
        "retrieval_query": query,
        "retrieved_chunks": [
            {
                "chunk_id": "eval-report-chunk-001",
                "file_name": "颜色选择.txt",
                "content": "用于 eval report 的知识库资料。",
                "score": 0.1,
            }
        ],
        "source_count": 1,
    }


def fake_policy_runner(query):
    return {
        "has_policy_source": False,
        "policy_answer": "当前知识库没有退换货、物流或售后政策资料，建议联系人工客服确认。",
        "retrieval_query": query,
        "policy_chunks": [],
        "raw_retrieved_chunks": [],
        "source_count": 0,
        "reason": "eval report no policy source",
    }


def fake_size_runner(query, chat_history=None):
    return {
        "recommended_size": "L",
        "reason": "eval report size",
        "alternative": "XL" if "宽松" in query else None,
        "match_type": "exact",
        "preference": None,
        "size_query": query,
        "measurements": {},
        "raw_match": {},
    }


def fake_answer_generator(state):
    return f"eval report answer for {state.intent_result['intent']}", "eval report prompt"


def build_fake_tool_registry():
    """构建评测专用工具表。

    Learning: 这里复用真实 ToolRegistry，只替换底层 runner，
    所以测到的是同一套工具选择规则，而不是另一套测试逻辑。
    """
    return build_default_tool_registry(
        rag_runner=fake_rag_runner,
        policy_runner=fake_policy_runner,
        size_runner=fake_size_runner,
    )


def evaluate_executor_case(case, executor_name, executor_fn, tool_registry, answer_generator):
    """执行单个 case，并把实际结果和期望契约比对成一行报告。"""
    result = executor_fn(
        case["query"],
        chat_history=case.get("chat_history"),
        tool_registry=tool_registry,
        answer_generator=answer_generator,
    )
    debug = result["debug"]
    actual_intent = debug["intent_result"]["intent"]
    actual_tools = debug["selected_tools"]
    actual_stop_reason = debug["stop_reason"]
    rag_chunk_count = len(debug["retrieved_chunks"])
    expected_rag_ok = rag_chunk_count > 0 if case["requires_rag"] else rag_chunk_count == 0
    passed = (
        actual_intent == case["expected_intent"]
        and actual_tools == case["expected_tools"]
        and actual_stop_reason == case["expected_stop_reason"]
        and expected_rag_ok
    )

    return {
        "case": case["name"],
        "query": case["query"],
        "executor": executor_name,
        "expected_intent": case["expected_intent"],
        "actual_intent": actual_intent,
        "expected_tools": case["expected_tools"],
        "actual_tools": actual_tools,
        "expected_stop_reason": case["expected_stop_reason"],
        "actual_stop_reason": actual_stop_reason,
        "requires_rag": case["requires_rag"],
        "rag_chunk_count": rag_chunk_count,
        "passed": passed,
    }


def build_consistency_rows(rows):
    """检查两个 executor 在同一个 case 上是否表现一致。"""
    rows_by_case = defaultdict(list)

    for row in rows:
        rows_by_case[row["case"]].append(row)

    consistency_rows = []

    for case_name, case_rows in rows_by_case.items():
        intents = {row["actual_intent"] for row in case_rows}
        tools = {tuple(row["actual_tools"]) for row in case_rows}
        stop_reasons = {row["actual_stop_reason"] for row in case_rows}
        rag_counts = {row["rag_chunk_count"] for row in case_rows}
        consistent = (
            len(intents) == 1
            and len(tools) == 1
            and len(stop_reasons) == 1
            and len(rag_counts) == 1
        )
        consistency_rows.append(
            {
                "case": case_name,
                "consistent": consistent,
                "intent_count": len(intents),
                "tools_count": len(tools),
                "stop_reason_count": len(stop_reasons),
                "rag_chunk_count_variants": len(rag_counts),
            }
        )

    return consistency_rows


def build_eval_report(
    cases=None,
    executors=None,
    tool_registry_factory=build_fake_tool_registry,
    answer_generator=fake_answer_generator,
):
    """生成完整评测报告数据。

    默认对比 pipeline 和 LangGraph shadow；传入参数可以让测试覆盖更小范围。
    """
    cases = cases or EVAL_CASES
    executors = executors or DEFAULT_EXECUTORS
    rows = []

    for case in cases:
        for executor_name, executor_fn in executors.items():
            rows.append(
                evaluate_executor_case(
                    case,
                    executor_name,
                    executor_fn,
                    tool_registry_factory(),
                    answer_generator,
                )
            )

    consistency_rows = build_consistency_rows(rows)
    failed_count = sum(1 for row in rows if not row["passed"])
    inconsistent_case_count = sum(1 for row in consistency_rows if not row["consistent"])

    return {
        "summary": {
            "case_count": len(cases),
            "executor_count": len(executors),
            "row_count": len(rows),
            "pass_count": len(rows) - failed_count,
            "failed_count": failed_count,
            "consistent_case_count": len(consistency_rows) - inconsistent_case_count,
            "inconsistent_case_count": inconsistent_case_count,
        },
        "rows": rows,
        "consistency_rows": consistency_rows,
    }


def format_tools(tools):
    if not tools:
        return "-"

    return ",".join(tools)


def format_bool(value):
    return "PASS" if value else "FAIL"


def format_markdown_report(report):
    """把报告数据格式化成 Markdown，方便终端查看或后续保存到文件。"""
    summary = report["summary"]
    lines = [
        "# Agent Eval Report",
        "",
        "## Summary",
        "",
        f"- Cases: {summary['case_count']}",
        f"- Executors: {summary['executor_count']}",
        f"- Rows: {summary['row_count']}",
        f"- Passed Rows: {summary['pass_count']}",
        f"- Failed Rows: {summary['failed_count']}",
        f"- Consistent Cases: {summary['consistent_case_count']}",
        f"- Inconsistent Cases: {summary['inconsistent_case_count']}",
        "",
        "## Executor Results",
        "",
        "| Case | Executor | Intent | Tools | Stop Reason | RAG Chunks | Pass |",
        "| --- | --- | --- | --- | --- | ---: | --- |",
    ]

    for row in report["rows"]:
        lines.append(
            "| {case} | {executor} | {intent} | {tools} | {stop} | {chunks} | {passed} |".format(
                case=row["case"],
                executor=row["executor"],
                intent=row["actual_intent"],
                tools=format_tools(row["actual_tools"]),
                stop=row["actual_stop_reason"],
                chunks=row["rag_chunk_count"],
                passed=format_bool(row["passed"]),
            )
        )

    lines.extend(
        [
            "",
            "## Executor Consistency",
            "",
            "| Case | Consistent | Intent Variants | Tool Variants | Stop Variants | RAG Count Variants |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )

    for row in report["consistency_rows"]:
        lines.append(
            "| {case} | {consistent} | {intent_count} | {tools_count} | {stop_count} | {rag_count} |".format(
                case=row["case"],
                consistent=format_bool(row["consistent"]),
                intent_count=row["intent_count"],
                tools_count=row["tools_count"],
                stop_count=row["stop_reason_count"],
                rag_count=row["rag_chunk_count_variants"],
            )
        )

    return "\n".join(lines)


def format_json_report(report):
    return json.dumps(report, ensure_ascii=False, indent=2)


def format_report(report, output_format):
    if output_format == "markdown":
        return format_markdown_report(report)

    if output_format == "json":
        return format_json_report(report)

    raise ValueError(f"Unsupported report format: {output_format}")


def write_report(report, output_format, output_path):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered_report = format_report(report, output_format)
    path.write_text(rendered_report, encoding="utf-8")
    return path


def build_arg_parser():
    parser = argparse.ArgumentParser(description="Generate deterministic Agent eval report.")
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Report output format. Defaults to markdown.",
    )
    parser.add_argument(
        "--output",
        help="Optional output path. When omitted, the report is printed to stdout.",
    )
    return parser


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    report = build_eval_report()

    if args.output:
        output_path = write_report(report, args.format, args.output)
        print(f"Report written to {output_path}")
        return

    print(format_report(report, args.format))


if __name__ == "__main__":
    main()
