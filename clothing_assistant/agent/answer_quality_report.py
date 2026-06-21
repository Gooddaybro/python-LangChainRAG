"""Answer quality report for the LangGraph clothing assistant.

The deterministic eval report checks whether the graph walks the right path.
This module checks whether the final user-visible answer is acceptable for
core commerce and RAG scenarios.
"""

import argparse
import json
from pathlib import Path

from clothing_assistant.agent.answer_quality_cases import ANSWER_QUALITY_CASES
from clothing_assistant.agent.langgraph_executor import run_langgraph_agent
from clothing_assistant.agent.tool_registry import build_default_tool_registry


DEBUG_LEAK_TERMS = [
    "trace_events",
    "selected_tools",
    "accepted_chunks",
    "rejected_chunks",
    "intent_result",
    "structured_result",
    "tool_results",
]


def fake_rag_runner(query, query_type=None):
    if "洗" in query:
        return {
            "retrieval_query": query,
            "retrieved_chunks": [
                {
                    "chunk_id": "answer-quality-care-001",
                    "file_name": "洗涤养护.txt",
                    "content": "纯棉T恤建议冷水或温水轻柔洗涤，反面晾晒，避免高温烘干。",
                    "score": 0.1,
                }
            ],
            "source_count": 1,
        }

    return {
        "retrieval_query": query,
        "retrieved_chunks": [
            {
                "chunk_id": "answer-quality-color-001",
                "file_name": "颜色选择.txt",
                "content": "日常通勤可以优先选择黑色、藏青色或灰色，整体更稳妥百搭。",
                "score": 0.1,
            }
        ],
        "source_count": 1,
    }


def weak_rag_runner(query, query_type=None):
    return {
        "retrieval_query": query,
        "retrieved_chunks": [
            {
                "chunk_id": "answer-quality-weak-001",
                "file_name": "无关资料.txt",
                "content": "这段资料和用户问题没有可靠关系。",
                "score": 0.95,
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
        "reason": "answer quality report no policy source",
    }


def fake_size_runner(query, chat_history=None):
    return {
        "recommended_size": "L",
        "reason": "如果想要宽松穿着，可以优先看 L 码并确认肩宽、胸围。",
        "alternative": "XL" if "宽松" in query else None,
        "match_type": "exact",
        "preference": "loose" if "宽松" in query else None,
        "size_query": query,
        "measurements": {"height_cm": 168, "weight_jin": 130},
        "raw_match": {},
    }


def fake_answer_generator(state):
    query = state["user_query"]

    if "怎么洗" in query:
        return (
            "纯棉T恤建议冷水或温水轻柔洗，反面晾晒，避免高温烘干。",
            "answer quality fake care prompt",
        )

    if "通勤" in query and "颜色" in query:
        return (
            "日常通勤可以优先选黑色、藏青色或灰色，黑色更稳妥百搭。",
            "answer quality fake color prompt",
        )

    return "我会基于已接受证据给出保守建议。", "answer quality fake prompt"


def build_fake_tool_registry(fixture_name=None):
    rag_runner = weak_rag_runner if fixture_name == "weak_rag" else fake_rag_runner
    return build_default_tool_registry(
        rag_runner=rag_runner,
        policy_runner=fake_policy_runner,
        size_runner=fake_size_runner,
    )


def resolve_grounding(debug):
    selected_tools = debug.get("selected_tools", [])

    if "structured_lookup" in selected_tools:
        return "structured_lookup"

    if "rag_tool" in selected_tools:
        return "rag_tool"

    if "size_tool" in selected_tools:
        return "size_tool"

    if "policy_tool" in selected_tools:
        return "policy_tool"

    return "direct_answer"


def score_answer(answer, debug, case):
    failures = []
    must_include = case.get("must_include", [])
    must_not_include = list(case.get("must_not_include", []))
    expected_grounding = case.get("expected_grounding")
    expected_stop_reason = case.get("expected_stop_reason")
    max_answer_length = case.get("max_answer_length")

    for text in must_include:
        if text not in answer:
            failures.append(
                {
                    "reason": "missing_required_text",
                    "text": text,
                }
            )

    for text in must_not_include:
        if text in answer:
            failures.append(
                {
                    "reason": "contains_forbidden_text",
                    "text": text,
                }
            )

    for text in DEBUG_LEAK_TERMS:
        if text in answer:
            failures.append(
                {
                    "reason": "debug_leak",
                    "text": text,
                }
            )

    actual_grounding = resolve_grounding(debug)
    if expected_grounding and actual_grounding != expected_grounding:
        failures.append(
            {
                "reason": "unexpected_grounding",
                "expected": expected_grounding,
                "actual": actual_grounding,
            }
        )

    actual_stop_reason = debug.get("stop_reason")
    if expected_stop_reason and actual_stop_reason != expected_stop_reason:
        failures.append(
            {
                "reason": "unexpected_stop_reason",
                "expected": expected_stop_reason,
                "actual": actual_stop_reason,
            }
        )

    if max_answer_length is not None and len(answer) > max_answer_length:
        failures.append(
            {
                "reason": "answer_too_long",
                "max": max_answer_length,
                "actual": len(answer),
            }
        )

    return {
        "passed": not failures,
        "failures": failures,
        "actual_grounding": actual_grounding,
        "actual_stop_reason": actual_stop_reason,
        "answer_length": len(answer),
    }


def evaluate_answer_quality_case(
    case,
    agent_runner=run_langgraph_agent,
    tool_registry_factory=build_fake_tool_registry,
    answer_generator=fake_answer_generator,
):
    try:
        result = agent_runner(
            case["query"],
            chat_history=case.get("chat_history"),
            tool_registry=tool_registry_factory(case.get("tool_fixture")),
            answer_generator=answer_generator,
        )
        answer = result["answer"]
        debug = result["debug"]
        score = score_answer(answer, debug, case)
        return {
            "case": case["name"],
            "query": case["query"],
            "answer_type": case["answer_type"],
            "answer": answer,
            "expected_grounding": case.get("expected_grounding"),
            "actual_grounding": score["actual_grounding"],
            "expected_stop_reason": case.get("expected_stop_reason"),
            "actual_stop_reason": score["actual_stop_reason"],
            "answer_length": score["answer_length"],
            "passed": score["passed"],
            "failures": score["failures"],
            "debug_summary": {
                "selected_tools": debug.get("selected_tools", []),
                "stop_reason": debug.get("stop_reason"),
                "retrieval_route": debug.get("retrieval_route", {}),
                "structured_lookup": {
                    "lookup_type": debug.get("structured_result", {}).get("lookup_type"),
                    "matched_product_name": debug.get("structured_result", {}).get("matched_product_name"),
                    "stock_count": debug.get("structured_result", {}).get("stock_count"),
                    "price_cny": debug.get("structured_result", {}).get("price_cny"),
                },
            },
        }
    except Exception as error:  # pragma: no cover - covered through report behavior.
        return {
            "case": case["name"],
            "query": case["query"],
            "answer_type": case["answer_type"],
            "answer": "",
            "expected_grounding": case.get("expected_grounding"),
            "actual_grounding": None,
            "expected_stop_reason": case.get("expected_stop_reason"),
            "actual_stop_reason": None,
            "answer_length": 0,
            "passed": False,
            "failures": [
                {
                    "reason": "runtime_error",
                    "message": str(error),
                }
            ],
            "debug_summary": {},
        }


def build_answer_quality_report(
    cases=None,
    agent_runner=run_langgraph_agent,
    tool_registry_factory=build_fake_tool_registry,
    answer_generator=fake_answer_generator,
):
    cases = cases or ANSWER_QUALITY_CASES
    rows = [
        evaluate_answer_quality_case(
            case,
            agent_runner=agent_runner,
            tool_registry_factory=tool_registry_factory,
            answer_generator=answer_generator,
        )
        for case in cases
    ]
    failed_count = sum(1 for row in rows if not row["passed"])

    return {
        "summary": {
            "case_count": len(cases),
            "pass_count": len(rows) - failed_count,
            "failed_count": failed_count,
        },
        "rows": rows,
    }


def format_bool(value):
    return "PASS" if value else "FAIL"


def format_failures(failures):
    if not failures:
        return "-"

    return ", ".join(failure["reason"] for failure in failures)


def format_markdown_report(report):
    summary = report["summary"]
    lines = [
        "# Answer Quality Report",
        "",
        "## Summary",
        "",
        f"- Cases: {summary['case_count']}",
        f"- Passed: {summary['pass_count']}",
        f"- Failed: {summary['failed_count']}",
        "",
        "## Results",
        "",
        "| Case | Type | Grounding | Stop Reason | Length | Pass | Failures |",
        "| --- | --- | --- | --- | ---: | --- | --- |",
    ]

    for row in report["rows"]:
        lines.append(
            "| {case} | {answer_type} | {grounding} | {stop_reason} | {length} | {passed} | {failures} |".format(
                case=row["case"],
                answer_type=row["answer_type"],
                grounding=row["actual_grounding"],
                stop_reason=row["actual_stop_reason"],
                length=row["answer_length"],
                passed=format_bool(row["passed"]),
                failures=format_failures(row["failures"]),
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
    path.write_text(format_report(report, output_format), encoding="utf-8")
    return path


def build_arg_parser():
    parser = argparse.ArgumentParser(description="Generate answer quality report.")
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
    report = build_answer_quality_report()

    if args.output:
        output_path = write_report(report, args.format, args.output)
        print(f"Report written to {output_path}")
        return

    print(format_report(report, args.format))


if __name__ == "__main__":
    main()

