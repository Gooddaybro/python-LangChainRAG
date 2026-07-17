"""Evaluate real vector retrieval separately from routing and answer quality."""

import argparse
import json
from pathlib import Path

from clothing_assistant.agent.retrieval_eval_cases import RETRIEVAL_EVAL_CASES
from clothing_assistant.config_data import RAG_DISTANCE_THRESHOLD, RAG_TOP_K
from clothing_assistant.tools.rag_tool import run_rag_tool


def accepted_chunks(chunks, threshold):
    return [chunk for chunk in chunks if float(chunk.get("score", 1.0)) <= threshold]


def expected_chunk_matches(chunk, case):
    if chunk.get("file_name") not in case["expected_file_names"]:
        return False

    keywords = case.get("expected_keywords_any", [])
    content = chunk.get("content", "")
    return not keywords or any(keyword in content for keyword in keywords)


def evaluate_retrieval_case(
    case,
    retriever=run_rag_tool,
    top_k=RAG_TOP_K,
    threshold=RAG_DISTANCE_THRESHOLD,
):
    result = retriever(
        case["query"],
        top_k=top_k,
        query_type=case["query_type"],
    )
    retrieved = result.get("retrieved_chunks", [])
    accepted = accepted_chunks(retrieved, threshold)
    hit = any(expected_chunk_matches(chunk, case) for chunk in accepted)
    false_accept = not case["should_retrieve"] and bool(accepted)
    passed = hit if case["should_retrieve"] else not false_accept

    return {
        "case": case["name"],
        "query": case["query"],
        "query_type": case["query_type"],
        "retrieval_query": result.get("retrieval_query"),
        "retrieved_chunks": retrieved,
        "accepted_chunks": accepted,
        "hit": hit,
        "false_accept": false_accept,
        "passed": passed,
    }


def build_retrieval_eval_report(
    cases=None,
    retriever=run_rag_tool,
    top_k=RAG_TOP_K,
    threshold=RAG_DISTANCE_THRESHOLD,
):
    cases = cases or RETRIEVAL_EVAL_CASES
    rows = [
        evaluate_retrieval_case(
            case,
            retriever=retriever,
            top_k=top_k,
            threshold=threshold,
        )
        for case in cases
    ]
    positive_rows = [row for row, case in zip(rows, cases) if case["should_retrieve"]]
    negative_rows = [row for row, case in zip(rows, cases) if not case["should_retrieve"]]
    positive_hits = sum(1 for row in positive_rows if row["hit"])
    false_accepts = sum(1 for row in negative_rows if row["false_accept"])
    pass_count = sum(1 for row in rows if row["passed"])

    return {
        "summary": {
            "case_count": len(rows),
            "positive_case_count": len(positive_rows),
            "positive_hit_count": positive_hits,
            "hit_rate": positive_hits / len(positive_rows) if positive_rows else 0.0,
            "negative_case_count": len(negative_rows),
            "false_accept_count": false_accepts,
            "false_accept_rate": false_accepts / len(negative_rows) if negative_rows else 0.0,
            "pass_count": pass_count,
            "failed_count": len(rows) - pass_count,
            "top_k": top_k,
            "threshold": threshold,
        },
        "rows": rows,
    }


def format_chunks(chunks):
    if not chunks:
        return "-"

    return "<br>".join(
        f"{chunk.get('file_name')}/{chunk.get('chunk_id')}@{float(chunk.get('score', 1.0)):.4f}"
        for chunk in chunks
    )


def format_markdown_report(report):
    summary = report["summary"]
    lines = [
        "# RAG Retrieval Report",
        "",
        "## Summary",
        "",
        f"- Cases: {summary.get('case_count', 0)}",
        f"- Positive hits: {summary.get('positive_hit_count', 0)}",
        f"- Hit rate: {summary.get('hit_rate', 0.0):.2%}",
        f"- False accepts: {summary.get('false_accept_count', 0)}",
        f"- False accept rate: {summary.get('false_accept_rate', 0.0):.2%}",
        f"- Top K: {summary.get('top_k', RAG_TOP_K)}",
        f"- Distance threshold: {summary.get('threshold', RAG_DISTANCE_THRESHOLD)}",
        "",
        "## Results",
        "",
        "| Case | Accepted Chunks | Hit | False Accept | Pass |",
        "| --- | --- | --- | --- | --- |",
    ]

    for row in report["rows"]:
        lines.append(
            "| {case} | {chunks} | {hit} | {false_accept} | {passed} |".format(
                case=row["case"],
                chunks=format_chunks(row.get("accepted_chunks", [])),
                hit="YES" if row.get("hit") else "NO",
                false_accept="YES" if row.get("false_accept") else "NO",
                passed="PASS" if row.get("passed") else "FAIL",
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
    parser = argparse.ArgumentParser(description="Generate real RAG retrieval report.")
    parser.add_argument("--top-k", type=int, default=RAG_TOP_K)
    parser.add_argument("--threshold", type=float, default=RAG_DISTANCE_THRESHOLD)
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--output")
    return parser


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    report = build_retrieval_eval_report(top_k=args.top_k, threshold=args.threshold)

    if args.output:
        output_path = write_report(report, args.format, args.output)
        print(f"Report written to {output_path}")
        return

    print(format_report(report, args.format))


if __name__ == "__main__":
    main()
