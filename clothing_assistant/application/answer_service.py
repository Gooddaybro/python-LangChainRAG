"""Shared answer construction for the legacy pipeline and LangGraph nodes."""

from langchain_core.messages import HumanMessage, SystemMessage

from clothing_assistant.agent.router import INTENT_CHAT, INTENT_UNKNOWN
from clothing_assistant.agent.tracing import persist_trace_if_enabled
from clothing_assistant.application.recommendation_service import build_product_rerank_result
from clothing_assistant.infrastructure.llm_client import get_chat_model


GENDER_LABELS = {"male": "男性", "female": "女性"}
SEASON_LABELS = {
    "spring": "春季",
    "summer": "夏季",
    "autumn": "秋季",
    "winter": "冬季",
    "all_season": "四季",
}
STYLE_LABELS = {"casual": "休闲", "minimal": "简约", "formal": "正式"}
FIT_LABELS = {"relaxed": "略宽松", "regular": "合身", "slim": "修身"}


def is_outfit_advice(intent_result, demand_intent=None):
    request_type = (demand_intent or {}).get("requestType") or (intent_result or {}).get("request_type")
    return str(request_type or "").strip().upper() == "OUTFIT_ADVICE"


def format_measurement(value):
    if not isinstance(value, (int, float)):
        return None
    return f"{value:g}"


def build_outfit_advice_draft(state):
    """Compose an inventory-safe outfit answer in the documented fixed order."""
    intent_result = state.get("intent_result") or {}
    demand_intent = state.get("demand_intent") or {}
    if not is_outfit_advice(intent_result, demand_intent):
        return None

    measurements = demand_intent.get("subjectMeasurements") or demand_intent.get("subject_measurements") or {}
    confirmation = []
    gender = str(demand_intent.get("targetGender") or "").lower()
    season = str(demand_intent.get("season") or "").lower()
    styles = demand_intent.get("style") or []
    fits = demand_intent.get("fitPreferences") or demand_intent.get("fit_preferences") or []
    height = format_measurement(measurements.get("heightCm") or measurements.get("height_cm"))
    weight = format_measurement(measurements.get("weightKg") or measurements.get("weight_kg"))

    if gender in GENDER_LABELS:
        confirmation.append(GENDER_LABELS[gender])
    if height:
        confirmation.append(f"{height}cm")
    if weight:
        confirmation.append(f"{weight}kg")
    if season in SEASON_LABELS:
        confirmation.append(SEASON_LABELS[season])
    confirmation.extend(STYLE_LABELS.get(str(value).lower(), str(value)) for value in styles if value)
    confirmation.extend(FIT_LABELS.get(str(value).lower(), str(value)) for value in fits if value)

    normalized_notice = ""
    if str(measurements.get("normalizedFrom") or measurements.get("normalized_from") or "").upper() == "ASSUMED_JIN" and weight:
        weight_jin = format_measurement(float(weight) * 2)
        normalized_notice = f"（原文体重 {weight_jin}斤，已按斤换算为 {weight}kg）"

    relaxed = "relaxed" in {str(value).lower() for value in fits}
    top_fit = "略宽松上衣" if relaxed else "合身上衣"
    formula = f"{top_fit} + 直筒下装"
    if season == "summer":
        material_advice = "优先轻薄、透气材质；上衣不过长，宽松但避免过度肥大。"
    elif season == "winter":
        material_advice = "用保暖内层叠加有结构的外搭，下装保持直筒，避免整体过度臃肿。"
    else:
        material_advice = "上衣长度和松量保持利落，下装优先直筒版型，材质按实际温度调整。"
    color_advice = "基础色上衣可搭卡其、深灰或藏青下装，全身控制在两到三种主色。"

    rerank_result = build_product_rerank_result(
        state.get("candidates") or [],
        intent_result,
        state.get("user_query") or "",
        state.get("user_context") or {},
        state.get("tool_results") or {},
        demand_intent=demand_intent,
    )
    refs = rerank_result["product_refs"]
    candidate_by_key = {
        (candidate.get("spu_id"), candidate.get("sku_id")): candidate
        for candidate in state.get("candidates") or []
    }
    product_lines = []
    for ref in refs:
        candidate = candidate_by_key.get((ref.get("spu_id"), ref.get("sku_id")))
        if not candidate:
            continue
        name = candidate.get("name") or "候选商品"
        price = candidate.get("sale_price")
        price_text = f"（{price:g} 元）" if isinstance(price, (int, float)) else ""
        reason = str(ref.get("reason") or "符合当前明确需求。")
        if reason.startswith(f"{name}："):
            reason = reason.removeprefix(f"{name}：")
        product_lines.append(f"   - {name}{price_text}：{reason}")

    if not product_lines:
        product_lines.append("   当前没有可归因的强匹配商品；先按以上方法搭配，不补造商品。")

    capabilities = demand_intent.get("requestedCapabilities") or intent_result.get("requested_capabilities") or []
    size_line = []
    if "SIZE_GUIDANCE" in capabilities:
        size = ((state.get("tool_results") or {}).get("size_tool") or {}).get("recommended_size")
        if size:
            size_line.append(f"5. 尺码提示：当前规则建议优先参考 {size} 码，具体仍以商品尺码表为准。")

    follow_up_number = 6 if size_line else 5
    summary = "、".join(confirmation) if confirmation else "当前"
    return "\n".join(
        [
            f"1. 需求确认：按{summary}的穿搭需求{normalized_notice}。",
            f"2. 搭配公式：{formula}。",
            f"3. 版型、材质与颜色：{material_advice}{color_advice}",
            "4. 可购买商品：",
            *product_lines,
            *size_line,
            f"{follow_up_number}. 可选追问：你更偏日常休闲，还是通勤利落？",
        ]
    )


def format_rag_sources(chunks):
    """Build deterministic user-facing citations from accepted RAG chunks.

    The application, rather than the chat model, creates these citations so a
    generated answer cannot claim a file or chunk that retrieval did not pass.

    Args:
        chunks: Accepted retrieval chunks containing ``file_name`` and ``chunk_id``.

    Returns:
        A deduplicated citation string, or an empty string when no valid source exists.
    """
    seen = set()
    sources = []

    for chunk in chunks or []:
        file_name = chunk.get("file_name")
        chunk_id = chunk.get("chunk_id")
        key = (file_name, chunk_id)

        if not file_name or not chunk_id or key in seen:
            continue

        seen.add(key)
        sources.append(f"{file_name}（{chunk_id}）")

    return "、".join(sources)


def append_rag_sources(answer, chunks):
    """Append citations only when deterministic accepted-RAG sources exist.

    Args:
        answer: User-facing answer that passed the answer validator.
        chunks: Accepted RAG chunks used as the only valid citation inputs.

    Returns:
        The original answer when no source is available; otherwise the answer
        followed by a deterministic source footer.
    """
    sources = format_rag_sources(chunks)
    if not sources:
        return answer

    return f"{answer}\n\n参考资料：{sources}"


def format_chunks(chunks):
    """把 RAG chunk 转成最终 prompt 可读的中文资料块。"""
    if not chunks:
        return "无可用知识库资料。"

    lines = []

    for index, chunk in enumerate(chunks, start=1):
        lines.append(
            "\n".join(
                [
                    f"资料{index}",
                    f"来源：{chunk['file_name']} | {chunk['chunk_id']}",
                    f"内容：{chunk['content']}",
                ]
            )
        )

    return "\n\n".join(lines)


def build_final_prompt(user_query, intent_result, memory_result, tool_results):
    """组装最终给大模型的上下文。"""
    rag_result = tool_results.get("rag_tool")
    size_result = tool_results.get("size_tool")
    policy_result = tool_results.get("policy_tool")

    rag_context = "未调用 RAG 工具。"

    if rag_result:
        rag_context = format_chunks(rag_result["retrieved_chunks"])

    return f"""
你是一个电商服装导购客服 Agent。
你必须基于工具结果回答，不要编造知识库外的信息。
如果工具结果不足，直接说明需要用户补充或联系人工客服。

用户问题：
{user_query}

意图判断：
{intent_result}

有效历史：
{memory_result["used_history"]}

RAG 检索资料：
{rag_context}

尺码工具结果：
{size_result}

政策工具结果：
{policy_result}

回答要求：
1. 中文回答，简洁，像客服。
2. 如果有 RAG 资料，先结合商品属性。
3. 如果问题需要尺码，再结合尺码工具结果。
4. 如果政策工具显示没有政策来源，不能编造退换货、物流、售后规则。
5. 如果尺码工具 match_type 是 measurement_conflict，只说明当前尺码表无法给出单一可靠尺码，引导用户补充胸围、肩宽、衣长或试穿确认，不要输出两个跨度很大的尺码作为推荐。
6. 不要输出 debug JSON，只输出给用户看的答案。
""".strip()


def build_answer_messages(final_prompt):
    """Build the shared provider message list for sync and streaming generation."""
    return [
        SystemMessage(content="你是可靠的电商服装导购客服 Agent。"),
        HumanMessage(content=final_prompt),
    ]


def generate_final_answer(user_query, intent_result, memory_result, tool_results):
    """调用真实聊天模型生成最终回答。测试里会用 fake answer_generator 替代它。"""
    final_prompt = build_final_prompt(user_query, intent_result, memory_result, tool_results)
    chat_model = get_chat_model()
    messages = build_answer_messages(final_prompt)
    response = chat_model.invoke(messages)

    return response.content, final_prompt


def default_answer_generator(state):
    outfit_answer = build_outfit_advice_draft(state)
    if outfit_answer:
        return outfit_answer, "outfit_advice deterministic draft"
    return generate_final_answer(
        state["user_query"],
        state["intent_result"],
        state["memory_result"],
        state["tool_results"],
    )


def build_direct_answer(user_query, intent_result):
    """不需要工具和大模型时直接回答。"""
    if intent_result["intent"] == INTENT_CHAT:
        return "我是服装导购助手，可以帮你做尺码推荐、颜色搭配、洗涤养护和基础商品咨询。"

    if intent_result["intent"] == INTENT_UNKNOWN:
        return "这个问题我暂时无法准确判断。你可以补充想咨询的是尺码、颜色、洗涤、库存还是售后政策。"

    return None


def build_response_from_state(state, trace_events=None):
    """把内部 State 转成外部调用方稳定使用的 response/debug 结构。"""
    traces = trace_events if trace_events is not None else state.get("trace_events", [])
    persist_trace_if_enabled(state, traces)
    return build_agent_response(
        state["answer"],
        state["user_query"],
        state["intent_result"],
        state["selected_tools"],
        state["memory_result"],
        state["tool_results"],
        state["final_prompt"],
        stop_reason=state.get("stop_reason"),
        tool_call_count=state.get("tool_call_count", 0),
        trace_events=traces,
        request_id=state.get("request_id"),
        session_id=state.get("session_id"),
        thread_id=state.get("thread_id"),
        run_id=state.get("run_id"),
        user_context=state.get("user_context", {}),
        candidates=state.get("candidates", []),
        demand_intent=state.get("demand_intent", {}),
        missing_info_result=state.get("missing_info_result", {}),
        structured_result=state.get("structured_result", {}),
        accepted_chunks=state.get("accepted_chunks", []),
        rejected_chunks=state.get("rejected_chunks", []),
        retrieval_route=state.get("retrieval_route", {}),
        draft_answer=state.get("draft_answer", ""),
        validation_result=state.get("validation_result", {}),
        generation_attempts=state.get("generation_attempts", 0),
        validation_feedback=state.get("validation_feedback", ""),
        fallback_result=state.get("fallback_result", {}),
        evidence_summary=state.get("evidence_summary", {}),
    )


def build_agent_response(
        answer,
        user_query,
        intent_result,
        selected_tools,
        memory_result,
        tool_results,
        final_prompt,
        stop_reason=None,
        tool_call_count=0,
        trace_events=None,
        request_id=None,
        session_id=None,
        thread_id=None,
        run_id=None,
        user_context=None,
        candidates=None,
        demand_intent=None,
        missing_info_result=None,
        structured_result=None,
        accepted_chunks=None,
        rejected_chunks=None,
        retrieval_route=None,
        draft_answer=None,
        validation_result=None,
        generation_attempts=0,
        validation_feedback=None,
        fallback_result=None,
        evidence_summary=None,
):
    """统一 Agent 输出契约。"""
    rag_result = tool_results.get("rag_tool") or {}
    rerank_result = build_product_rerank_result(
        candidates,
        intent_result,
        user_query,
        user_context,
        tool_results,
        demand_intent=demand_intent,
    )
    product_refs = rerank_result["product_refs"]
    rejected_reasons = rerank_result["rejected_reasons"]

    return {
        "answer": answer,
        "product_refs": product_refs,
        "rejected_reasons": rejected_reasons,
        "debug": {
            "user_query": user_query,
            "request_id": request_id,
            "session_id": session_id,
            "thread_id": thread_id,
            "run_id": run_id,
            "user_context": user_context or {},
            "candidates": candidates or [],
            "demand_intent": demand_intent or {},
            "product_refs": product_refs,
            "selected_product_refs": product_refs,
            "rejected_reasons": rejected_reasons,
            "semantic_preferences": rerank_result["semantic_preferences"],
            "candidate_scores": rerank_result["candidate_scores"],
            "recommendation_source": rerank_result["recommendation_source"],
            "intent_result": intent_result,
            "selected_tools": selected_tools,
            "used_history": memory_result["used_history"],
            "ignored_history_reason": memory_result["ignored_history_reason"],
            "retrieval_query": rag_result.get("retrieval_query"),
            "retrieved_chunks": rag_result.get("retrieved_chunks", []),
            "rag_meta": rag_result.get("rag_meta", {}),
            "missing_info_result": missing_info_result or {},
            "structured_result": structured_result or {},
            "accepted_chunks": accepted_chunks or [],
            "rejected_chunks": rejected_chunks or [],
            "retrieval_route": retrieval_route or {},
            "draft_answer": draft_answer or "",
            "validation_result": validation_result or {},
            "generation_attempts": generation_attempts,
            "validation_feedback": validation_feedback or "",
            "fallback_result": fallback_result or {},
            "evidence_summary": evidence_summary or {},
            "tool_results": tool_results,
            "tool_call_count": tool_call_count,
            "final_prompt": final_prompt,
            "stop_reason": stop_reason,
            "trace_events": trace_events or [],
        },
    }
