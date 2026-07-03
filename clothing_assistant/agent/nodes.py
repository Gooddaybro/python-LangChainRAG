"""LangGraph node functions for the clothing assistant graph.

The graph now separates exact business facts from semantic RAG knowledge:
catalog price/stock are handled by structured nodes, while styling, care and
product explanations still go through retrieval.
"""

from clothing_assistant.agent.agent_executor import (
    apply_direct_answer_gate,
    apply_fallback_rag_tool,
    apply_policy_fallback_gate,
    generate_pipeline_answer,
    resolve_memory,
    route_intent,
)
from clothing_assistant.application.answer_service import default_answer_generator
from clothing_assistant.agent.router import (
    INTENT_INVENTORY_CHECK,
    INTENT_POLICY_QA,
    INTENT_PRICE_CHECK,
    INTENT_RECOMMENDATION,
    INTENT_SIZE_RECOMMENDATION,
)
from clothing_assistant.agent.state import make_trace
from clothing_assistant.application.recommendation_service import build_product_refs
from clothing_assistant.agent.tool_registry import (
    build_default_tool_registry,
    execute_tool_spec,
    find_tool,
)
from clothing_assistant.size_matcher import has_complete_measurements
from clothing_assistant.tools.product_catalog import (
    extract_requested_color,
    extract_requested_size,
    find_matching_product,
    run_structured_lookup,
)
from clothing_assistant.tools.size_tool import normalize_measurement_query


RETRIEVAL_SCORE_THRESHOLD = 0.7
RAG_ALLOWED_SOURCES = {
    "recommendation": {"颜色选择.txt", "洗涤养护.txt", "尺码推荐.txt"},
    "product": {"颜色选择.txt", "洗涤养护.txt", "尺码推荐.txt"},
    "size": {"尺码推荐.txt", "颜色选择.txt"},
}


def route_intent_node(state):
    traces = route_intent(state)
    return {
        "intent_result": state["intent_result"],
        "trace_events": traces,
    }


def resolve_memory_node(state):
    traces = resolve_memory(state)
    return {
        "memory_result": state["memory_result"],
        "agent_query": state["agent_query"],
        "trace_events": traces,
    }


def direct_answer_node(state):
    stopped, traces = apply_direct_answer_gate(state)
    result = {"trace_events": traces}

    if stopped:
        result["answer"] = state["answer"]
        result["final_prompt"] = state["final_prompt"]
        result["stop_reason"] = state["stop_reason"]

    return result


def has_measurements_in_current_or_history(state):
    """尺码节点的前置检查：当前句子或 memory_tool 改写结果里必须有身高体重。"""
    user_query = normalize_measurement_query(state["user_query"])

    if has_complete_measurements(user_query):
        return True

    used_history = state.get("memory_result", {}).get("used_history", {})
    history_query = used_history.get("measurements_query")
    return bool(history_query and has_complete_measurements(history_query))


def build_missing_info_answer(missing_fields):
    if "product" in missing_fields:
        return "想查哪件商品？请补充商品名或 SKU，我再帮你查库存或价格。"

    if "color" in missing_fields and "size" in missing_fields:
        return "请补充颜色和尺码，例如“基础款纯棉T恤黑色 L 码有货吗”。"

    if "color" in missing_fields:
        return "请补充想查的颜色，例如黑色、白色或灰色。"

    if "size" in missing_fields:
        return "请补充想查的尺码，例如 M、L 或 XL。"

    if "measurements" in missing_fields:
        return "请补充身高和体重，我才能按尺码规则给你推荐。"

    return "请补充关键信息后我再帮你查询。"


def missing_info_gate_node(state):
    """生产图的缺信息门。

    Learning: 缺关键字段时直接返回追问，不让后续节点靠 prompt 自行猜商品、
    颜色或尺码。这是生产 Agent 比 demo 更可靠的关键边界。
    """
    intent = state["intent_result"]["intent"]
    missing_fields = []

    if intent in {INTENT_INVENTORY_CHECK, INTENT_PRICE_CHECK}:
        match_result = find_matching_product(state["user_query"])
        product = match_result.get("product")

        if not product or match_result.get("ambiguous"):
            missing_fields.append("product")
        elif intent == INTENT_INVENTORY_CHECK:
            if not extract_requested_color(state["user_query"], product):
                missing_fields.append("color")
            if not extract_requested_size(state["user_query"]):
                missing_fields.append("size")

    if intent == INTENT_SIZE_RECOMMENDATION and not has_measurements_in_current_or_history(state):
        missing_fields.append("measurements")

    result = {
        "missing_fields": missing_fields,
        "can_continue": not missing_fields,
    }

    if not missing_fields:
        return {
            "missing_info_result": result,
            "trace_events": make_trace("missing_info_gate", can_continue=True),
        }

    answer = build_missing_info_answer(missing_fields)
    return {
        "missing_info_result": result,
        "answer": answer,
        "final_prompt": "missing_info_gate 直接追问，不调用大模型。",
        "stop_reason": "missing_info",
        "trace_events": make_trace("missing_info_gate", can_continue=False, missing_fields=missing_fields),
    }


def tool_budget_available(state, max_tool_calls):
    return state.get("tool_call_count", 0) < max_tool_calls


def build_tool_update(state, tool_name, result_key, result):
    """把工具执行结果封装成 LangGraph update。

    Learning: 生产节点尽量返回“字段更新”，而不是依赖原地修改 state。
    这样 checkpointer 保存的每一步 state 更容易调试和回放。
    """
    selected_tools = list(state.get("selected_tools", []))
    tool_results = dict(state.get("tool_results", {}))
    tool_call_count = state.get("tool_call_count", 0) + 1
    selected_tools.append(tool_name)
    tool_results[result_key] = result
    traces = make_trace("tool_selected", tool=tool_name, tool_call_count=tool_call_count)
    traces.extend(
        make_trace(
            "tool_result",
            tool=tool_name,
            result_summary=summarize_result_for_trace(result),
        )
    )

    return {
        "selected_tools": selected_tools,
        "tool_call_count": tool_call_count,
        "tool_results": tool_results,
        "trace_events": traces,
    }


def summarize_result_for_trace(result):
    if not isinstance(result, dict):
        return {"type": type(result).__name__}

    summary = {}

    for key in [
        "lookup_type",
        "matched_product_id",
        "missing_fields",
        "source_count",
        "has_policy_source",
        "recommended_size",
        "retrieval_query",
    ]:
        if key in result:
            summary[key] = result[key]

    if "retrieved_chunks" in result:
        summary["retrieved_chunk_count"] = len(result["retrieved_chunks"])

    return summary


def run_catalog_lookup(state):
    structured_result = run_structured_lookup(
        state["user_query"],
        intent_result=state["intent_result"],
    )
    update = build_tool_update(
        state,
        "structured_lookup",
        "structured_lookup",
        structured_result,
    )
    update["structured_result"] = structured_result
    return update


def structured_lookup_node(state, registry=None, max_tool_calls=3):
    """执行结构化事实工具，也保留政策/尺码这类确定性工具入口。"""
    registry = registry or build_default_tool_registry()
    traces = []
    structured_result = state.get("structured_result", {})
    intent = state["intent_result"]["intent"]

    if not tool_budget_available(state, max_tool_calls):
        return {"trace_events": make_trace("tool_budget_reached", max_tool_calls=max_tool_calls)}

    if intent in {INTENT_INVENTORY_CHECK, INTENT_PRICE_CHECK}:
        return run_catalog_lookup(state)
    elif intent == INTENT_POLICY_QA:
        policy_tool = find_tool(registry, "policy_tool")
        if policy_tool and policy_tool.should_run(state):
            result = policy_tool.run(state)
            update = build_tool_update(state, policy_tool.name, policy_tool.result_key, result)
            update["structured_result"] = structured_result
            return update
    elif intent == INTENT_SIZE_RECOMMENDATION:
        size_tool = find_tool(registry, "size_tool")
        if size_tool and size_tool.should_run(state):
            result = size_tool.run(state)
            update = build_tool_update(state, size_tool.name, size_tool.result_key, result)
            update["structured_result"] = structured_result
            return update

    return {
        "structured_result": structured_result,
        "trace_events": make_trace("structured_lookup", skipped=True),
    }


def policy_fallback_node(state):
    stopped, traces = apply_policy_fallback_gate(state)
    result = {"trace_events": traces}

    if stopped:
        result["answer"] = state["answer"]
        result["final_prompt"] = state["final_prompt"]
        result["stop_reason"] = state["stop_reason"]

    return result


def should_run_rag_stage(state, registry=None):
    intent = state["intent_result"]["intent"]

    if intent in {INTENT_INVENTORY_CHECK, INTENT_PRICE_CHECK, INTENT_POLICY_QA}:
        return False

    rag_tool = find_tool(registry or build_default_tool_registry(), "rag_tool")
    return bool(rag_tool and rag_tool.should_run(state))


def rag_retriever_node(state, registry=None, max_tool_calls=3):
    """只在语义知识问题上检索 RAG，不处理价格和库存。"""
    registry = registry or build_default_tool_registry()
    rag_tool = find_tool(registry, "rag_tool")

    if not rag_tool or not should_run_rag_stage(state, registry):
        return {"trace_events": make_trace("rag_retriever", skipped=True)}

    if not tool_budget_available(state, max_tool_calls):
        return {"trace_events": make_trace("tool_budget_reached", max_tool_calls=max_tool_calls)}

    result = rag_tool.run(state)
    return build_tool_update(state, rag_tool.name, rag_tool.result_key, result)


def chunk_is_relevant(chunk, query_type):
    score = float(chunk.get("score", 1.0))
    file_name = chunk.get("file_name")
    allowed_sources = RAG_ALLOWED_SOURCES.get(query_type)

    if score > RETRIEVAL_SCORE_THRESHOLD:
        return False

    if allowed_sources and file_name not in allowed_sources:
        return False

    return True


def retrieval_grader_node(state):
    """规则版检索评分器。

    Learning: 第一版不用 LLM judge。先用确定性规则挡住明显弱证据，
    这样评测结果稳定，也能避免模型“看起来合理但无证据”的回答。
    """
    rag_result = state.get("tool_results", {}).get("rag_tool")

    if not rag_result:
        retrieval_route = {
            "status": "skipped",
            "reason": "rag_result_missing",
            "accepted_count": 0,
            "rejected_count": 0,
        }
        return {
            "accepted_chunks": [],
            "rejected_chunks": [],
            "retrieval_route": retrieval_route,
            "trace_events": make_trace("retrieval_grader", skipped=True, retrieval_route=retrieval_route),
        }

    query_type = state["intent_result"]["query_type"]
    chunks = rag_result.get("retrieved_chunks", [])
    accepted_chunks = [chunk for chunk in chunks if chunk_is_relevant(chunk, query_type)]
    rejected_chunks = [chunk for chunk in chunks if chunk not in accepted_chunks]
    tool_results = dict(state["tool_results"])
    graded_rag_result = dict(rag_result)
    graded_rag_result["retrieved_chunks"] = accepted_chunks
    graded_rag_result["source_count"] = len(accepted_chunks)
    tool_results["rag_tool"] = graded_rag_result
    if accepted_chunks:
        status = "good"
        reason = "accepted_chunks_available"
    elif chunks:
        status = "weak"
        reason = "all_retrieved_chunks_rejected"
    else:
        status = "empty"
        reason = "retrieved_chunks_empty"
    retrieval_route = {
        "status": status,
        "reason": reason,
        "accepted_count": len(accepted_chunks),
        "rejected_count": len(rejected_chunks),
    }

    return {
        "accepted_chunks": accepted_chunks,
        "rejected_chunks": rejected_chunks,
        "tool_results": tool_results,
        "retrieval_route": retrieval_route,
        "trace_events": make_trace(
            "retrieval_grader",
            accepted_count=len(accepted_chunks),
            rejected_count=len(rejected_chunks),
            retrieval_route=retrieval_route,
        ),
    }


def fallback_answer_node(state):
    retrieval_route = state.get("retrieval_route") or {}
    validation_result = state.get("validation_result") or {}

    if retrieval_route.get("status") in {"weak", "empty"}:
        answer = (
            "当前知识库没有检索到足够可靠的资料，暂时不能给出确定建议。"
            "你可以补充商品名、场景或联系人工客服确认。"
        )
        fallback_result = {
            "kind": "retrieval_fallback",
            "reason": retrieval_route.get("reason", "no accepted retrieval evidence"),
        }
        validation_result = {
            "grounded": False,
            "retryable": False,
            "reason": "no accepted retrieval evidence",
        }
    else:
        answer = (
            "当前回答没有通过证据校验，暂时不能给出确定结论。"
            "你可以补充商品、尺码、场景或联系人工客服确认。"
        )
        fallback_result = {
            "kind": "validation_fallback",
            "reason": validation_result.get("reason", "answer validation failed"),
        }

    return {
        "answer": answer,
        "final_prompt": fallback_result["kind"],
        "validation_result": validation_result,
        "fallback_result": fallback_result,
        "stop_reason": "answer_fallback",
        "trace_events": make_trace("fallback_answer", fallback_result=fallback_result),
    }


def build_candidate_recommendation_refs(state):
    return build_product_refs(
        state.get("candidates", []),
        state.get("intent_result", {}),
        state.get("user_query", ""),
        state.get("user_context", {}),
        state.get("tool_results", {}),
    )


def has_candidate_backed_recommendation(state):
    return (
        state.get("intent_result", {}).get("intent") == INTENT_RECOMMENDATION
        and bool(build_candidate_recommendation_refs(state))
    )


def build_candidate_recommendation_draft(state):
    refs = build_candidate_recommendation_refs(state)
    if not refs:
        return None

    candidate_by_sku = {
        candidate.get("sku_id"): candidate
        for candidate in state.get("candidates", [])
        if candidate.get("sku_id") is not None
    }
    lines = ["我从当前商品库候选里优先推荐："]

    for index, ref in enumerate(refs, start=1):
        candidate = candidate_by_sku.get(ref.get("sku_id"), {})
        name = candidate.get("name") or f"商品 {ref.get('spu_id')}"
        color = candidate.get("color")
        size = candidate.get("size")
        price = candidate.get("sale_price")
        details = " / ".join(str(value) for value in [color, size, f"{price:g} 元" if isinstance(price, (int, float)) else None] if value)
        prefix = f"{index}. {name}"
        if details:
            prefix = f"{prefix}（{details}）"
        reason = ref.get("reason", "符合当前筛选条件。")
        if isinstance(reason, str) and reason.startswith(f"{name}："):
            reason = reason.removeprefix(f"{name}：")
        lines.append(f"{prefix}：{reason}")

    return "\n".join(lines)


def build_structured_draft(structured_result):
    lookup_type = structured_result.get("lookup_type")
    name = structured_result.get("matched_product_name") or "这件商品"

    if lookup_type == "price" and structured_result.get("price_cny") is not None:
        return f"{name}的价格是 {structured_result['price_cny']} 元。"

    if lookup_type != "inventory":
        return None

    color = structured_result.get("color") or "该颜色"
    size = structured_result.get("size") or "该尺码"

    if "color_not_found" in structured_result.get("missing_fields", []):
        colors = "、".join(structured_result.get("available_colors", []))
        return f"{name}目前没有{color}的库存记录。当前可查颜色：{colors}。"

    if structured_result.get("stock_count") is None:
        return "库存查询还缺少颜色或尺码，请补充后再查。"

    stock_count = structured_result["stock_count"]

    if structured_result.get("in_stock"):
        return f"{name}{color} {size} 码有货，当前库存 {stock_count} 件。"

    return f"{name}{color} {size} 码当前无货。"


def build_size_recommendation_draft(state):
    size_result = state.get("tool_results", {}).get("size_tool") or {}
    recommended_size = size_result.get("recommended_size")

    if not recommended_size:
        return None

    reason = size_result.get("reason") or "已根据你的身高体重匹配尺码规则。"
    measurements = size_result.get("measurements") or {}
    height_cm = measurements.get("height_cm")
    weight_jin = measurements.get("weight_jin")
    measurement_text = "你提供的身高体重"

    if height_cm and weight_jin:
        measurement_text = f"{height_cm:g}cm、{weight_jin:g}斤"

    matching_candidates = [
        candidate
        for candidate in state.get("candidates", [])
        if str(candidate.get("size", "")).strip().upper() == str(recommended_size).strip().upper()
    ]

    if matching_candidates:
        names = "、".join(candidate.get("name", "候选商品") for candidate in matching_candidates[:3])
        return (
            f"按 {measurement_text}，建议优先看 {recommended_size} 码。"
            f"{reason} 当前候选里可以先看：{names}。"
        )

    return f"按 {measurement_text}，建议优先看 {recommended_size} 码。{reason}"


def answer_generator_node(state, answer_generator=None):
    """生成草稿答案，不直接作为最终答案。

    Learning: 生产图里 generator 只负责 draft，最终是否可用交给 validator。
    """
    answer_generator = answer_generator or default_answer_generator
    generation_attempts = state.get("generation_attempts", 0) + 1
    structured_result = state.get("structured_result") or {}
    structured_draft = build_structured_draft(structured_result)
    recommendation_draft = build_candidate_recommendation_draft(state)
    size_draft = build_size_recommendation_draft(state)

    if structured_draft:
        draft_answer = structured_draft
        final_prompt = "structured_lookup draft，不调用大模型。"
    elif recommendation_draft:
        draft_answer = recommendation_draft
        final_prompt = "java_candidate_recommendation draft，不调用大模型。"
    elif size_draft:
        draft_answer = size_draft
        final_prompt = "size_tool draft，不调用大模型。"
    elif state.get("tool_results", {}).get("rag_tool") and not state.get("accepted_chunks"):
        draft_answer = ""
        final_prompt = "retrieval_grader 没有接受的证据，等待后续兜底。"
    else:
        generator_state = dict(state)
        generator_state["generation_attempts"] = generation_attempts - 1
        generator_state["validation_feedback"] = state.get("validation_feedback", "")
        draft_answer, final_prompt = answer_generator(generator_state)

    return {
        "draft_answer": draft_answer,
        "final_prompt": final_prompt,
        "generation_attempts": generation_attempts,
        "trace_events": make_trace(
            "answer_generated",
            draft=True,
            generation_attempts=generation_attempts,
            validation_feedback=state.get("validation_feedback", ""),
        ),
    }


def answer_validator_node(state):
    """确定性答案校验器。

    价格/库存答案必须来自 structured_result；RAG 没有有效证据时不能编造。
    """
    structured_result = state.get("structured_result") or {}
    validation_result = {
        "grounded": True,
        "retryable": False,
        "reason": "draft accepted",
    }

    if structured_result.get("lookup_type") in {"price", "inventory"}:
        answer = build_structured_draft(structured_result) or state.get("draft_answer", "")
        validation_result["reason"] = "structured facts validated"
        return {
            "answer": answer,
            "validation_result": validation_result,
            "stop_reason": "final_answer",
            "trace_events": make_trace("answer_validated", grounded=True, source="structured_lookup"),
        }

    draft_answer = state.get("draft_answer", "")
    if not draft_answer.strip():
        validation_result = {
            "grounded": False,
            "retryable": True,
            "reason": "empty_draft_answer",
        }
        return {
            "validation_result": validation_result,
            "validation_feedback": "上一版回答为空，请基于已接受证据生成保守回答。",
            "trace_events": make_trace(
                "answer_validated",
                grounded=False,
                retryable=True,
                reason="empty_draft_answer",
            ),
        }

    if state.get("tool_results", {}).get("rag_tool") and not state.get("accepted_chunks"):
        if has_candidate_backed_recommendation(state):
            return {
                "answer": state.get("draft_answer", ""),
                "validation_result": validation_result,
                "stop_reason": "final_answer",
                "trace_events": make_trace("answer_validated", grounded=True, source="java_candidates"),
            }

        answer = "当前知识库没有检索到足够可靠的资料，暂时不能给出确定建议。你可以补充商品名、场景或联系人工客服确认。"
        validation_result = {
            "grounded": False,
            "retryable": False,
            "reason": "no accepted retrieval evidence",
        }
        return {
            "answer": answer,
            "validation_result": validation_result,
            "stop_reason": "answer_fallback",
            "trace_events": make_trace("answer_validated", grounded=False, source="rag_tool"),
        }

    return {
        "answer": state.get("draft_answer", ""),
        "validation_result": validation_result,
        "stop_reason": "final_answer",
        "trace_events": make_trace("answer_validated", grounded=True, source="draft_answer"),
    }


def trace_logger_node(state):
    """把本次运行的关键证据摘要写回 state，落盘仍由 tracing 模块控制。"""
    structured_result = state.get("structured_result") or {}
    evidence_summary = {
        "run_id": state.get("run_id"),
        "thread_id": state.get("thread_id"),
        "node_path": [event.get("step") for event in state.get("trace_events", [])],
        "selected_tools": state.get("selected_tools", []),
        "structured": {
            "lookup_type": structured_result.get("lookup_type"),
            "matched_product_id": structured_result.get("matched_product_id"),
            "stock_count": structured_result.get("stock_count"),
            "price_cny": structured_result.get("price_cny"),
        },
        "accepted_chunk_count": len(state.get("accepted_chunks", [])),
        "validation": state.get("validation_result", {}),
    }

    return {
        "evidence_summary": evidence_summary,
        "trace_events": make_trace("trace_logger", evidence_summary=evidence_summary),
    }


def execute_tools_node(state, registry=None, max_tool_calls=3):
    """兼容旧测试的节点。生产主图不再使用这个统一工具节点。"""
    registry = registry or build_default_tool_registry()
    traces = []

    for tool in registry:
        if not tool.should_run(state):
            continue

        if state.get("tool_call_count", 0) >= max_tool_calls:
            traces.extend(
                make_trace(
                    "tool_budget_reached",
                    max_tool_calls=max_tool_calls,
                    tool_call_count=state.get("tool_call_count", 0),
                )
            )
            break

        traces.extend(execute_tool_spec(state, tool))

    return {
        "selected_tools": state["selected_tools"],
        "tool_call_count": state["tool_call_count"],
        "tool_results": state["tool_results"],
        "trace_events": traces,
    }


def fallback_rag_node(state, registry=None):
    """兼容旧测试的节点。生产主图使用 rag_retriever_node。"""
    registry = registry or build_default_tool_registry()
    traces = apply_fallback_rag_tool(state, registry)
    result = {"trace_events": traces}

    if state.get("selected_tools"):
        result["selected_tools"] = state["selected_tools"]
        result["tool_call_count"] = state["tool_call_count"]
        result["tool_results"] = state["tool_results"]

    return result


def generate_answer_node(state, answer_generator=None):
    """兼容旧 pipeline 语义：直接生成最终 answer。"""
    answer_generator = answer_generator or default_answer_generator
    traces = generate_pipeline_answer(state, answer_generator)
    return {
        "answer": state["answer"],
        "final_prompt": state["final_prompt"],
        "stop_reason": state["stop_reason"],
        "trace_events": traces,
    }


def tool_budget_exhausted_node(state, max_tool_calls=3):
    return {
        "answer": "工具调用次数已达到上限，当前无法继续自动调用工具。",
        "final_prompt": "tool budget exhausted",
        "stop_reason": "tool_budget_exhausted",
        "trace_events": make_trace(
            "tool_budget_exhausted",
            max_tool_calls=max_tool_calls,
            tool_call_count=state.get("tool_call_count", 0),
        ),
    }


def route_after_direct_answer(state, max_tool_calls=3):
    if state.get("stop_reason"):
        return "stop"

    if state.get("tool_call_count", 0) >= max_tool_calls:
        return "budget_exhausted"

    return "missing_info"


def route_after_missing_info(state, max_tool_calls=3):
    if state.get("stop_reason"):
        return "stop"

    if state.get("tool_call_count", 0) >= max_tool_calls:
        return "budget_exhausted"

    return "structured_lookup"


def route_after_structured_lookup(state, registry=None, max_tool_calls=3):
    if state.get("stop_reason"):
        return "stop"

    if state["intent_result"]["intent"] == INTENT_POLICY_QA:
        return "policy_fallback"

    if should_run_rag_stage(state, registry):
        if state.get("tool_call_count", 0) >= max_tool_calls:
            return "budget_exhausted"
        return "rag_retriever"

    return "answer_generator"


def route_after_policy_fallback(state, max_tool_calls=3):
    if state.get("stop_reason"):
        return "stop"

    if state.get("tool_call_count", 0) >= max_tool_calls:
        return "budget_exhausted"

    return "answer_generator"


def route_after_retrieval_grader(state):
    status = (state.get("retrieval_route") or {}).get("status")

    if status == "good":
        return "answer_generator"

    if status in {"weak", "empty"} and has_candidate_backed_recommendation(state):
        return "answer_generator"

    if status in {"weak", "empty"}:
        return "fallback_answer"

    return "answer_generator"


def route_after_answer_validator(state):
    validation_result = state.get("validation_result") or {}

    if validation_result.get("grounded"):
        return "trace_logger"

    if validation_result.get("retryable") and state.get("generation_attempts", 0) < state.get("max_generation_attempts", 2):
        return "answer_generator"

    return "fallback_answer"
