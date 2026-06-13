"""Deterministic product reference selection for Java-provided candidates."""

from typing import Any

from clothing_assistant.agent.router import (
    INTENT_PRODUCT_QA,
    INTENT_RECOMMENDATION,
    INTENT_SIZE_RECOMMENDATION,
)


RECOMMENDABLE_INTENTS = {
    INTENT_PRODUCT_QA,
    INTENT_RECOMMENDATION,
    INTENT_SIZE_RECOMMENDATION,
}

IN_STOCK_STATUSES = {"in_stock", "low_stock", "available", "on_sale"}


def normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def normalize_size(value: Any) -> str:
    return str(value or "").strip().upper()


def as_number(value: Any) -> float | None:
    if value is None or value == "":
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def has_stock(candidate: dict[str, Any]) -> bool:
    available_stock = as_number(candidate.get("available_stock"))

    if available_stock is not None:
        return available_stock > 0

    stock_status = normalize_text(candidate.get("stock_status"))
    if not stock_status:
        return True

    return stock_status in IN_STOCK_STATUSES


def collect_query_terms(user_query: str, user_context: dict[str, Any]) -> set[str]:
    terms = set()
    normalized_query = normalize_text(user_query)

    for value in [
        "面试",
        "通勤",
        "日常",
        "显瘦",
        "宽松",
        "修身",
        "夏",
        "冬",
        "春",
        "秋",
    ]:
        if value.lower() in normalized_query:
            terms.add(value.lower())

    for key in ["preferred_styles", "preferred_colors", "preferred_categories"]:
        values = user_context.get(key) or []
        for value in values:
            if value:
                terms.add(normalize_text(value))

    return terms


def candidate_terms(candidate: dict[str, Any]) -> set[str]:
    terms = set()

    for key in ["name", "category", "color", "material", "fit_type"]:
        value = normalize_text(candidate.get(key))
        if value:
            terms.add(value)

    for key in ["season", "style_tags"]:
        for value in candidate.get(key) or []:
            normalized = normalize_text(value)
            if normalized:
                terms.add(normalized)

    return terms


def term_match_score(query_terms: set[str], candidate: dict[str, Any]) -> float:
    if not query_terms:
        return 0

    text = " ".join(candidate_terms(candidate))
    matched = sum(1 for term in query_terms if term and term in text)
    return matched / len(query_terms)


def get_recommended_size(tool_results: dict[str, Any]) -> str | None:
    size_result = tool_results.get("size_tool") or {}
    recommended_size = size_result.get("recommended_size")
    return normalize_size(recommended_size) if recommended_size else None


def get_alternative_size(tool_results: dict[str, Any]) -> str | None:
    size_result = tool_results.get("size_tool") or {}
    alternative_size = size_result.get("alternative")
    return normalize_size(alternative_size) if alternative_size else None


def candidate_size_match_type(
    candidate: dict[str, Any],
    recommended_size: str | None,
    alternative_size: str | None,
) -> str | None:
    if not recommended_size and not alternative_size:
        return "none"

    candidate_size = normalize_size(candidate.get("size"))
    if recommended_size and candidate_size == recommended_size:
        return "primary"

    if alternative_size and candidate_size == alternative_size:
        return "alternative"

    return None


def candidate_matches_size(
    candidate: dict[str, Any],
    recommended_size: str | None,
    alternative_size: str | None = None,
) -> bool:
    if not recommended_size and not alternative_size:
        return True

    return candidate_size_match_type(candidate, recommended_size, alternative_size) is not None


def build_reason(
    candidate: dict[str, Any],
    recommended_size: str | None,
    alternative_size: str | None,
    score_parts: list[str],
) -> str:
    name = candidate.get("name") or "这件商品"
    details = []
    match_type = candidate_size_match_type(candidate, recommended_size, alternative_size)

    if match_type == "primary":
        details.append(f"{recommended_size} 码匹配当前尺码建议")
    elif match_type == "alternative":
        details.append(f"{alternative_size} 码是当前尺码建议的备选范围")

    if has_stock(candidate):
        details.append("当前候选显示有库存")

    details.extend(score_parts)

    if not details:
        details.append("符合本轮 Java 候选商品条件")

    return f"{name}：" + "，".join(details) + "。"


def score_candidate(
    candidate: dict[str, Any],
    query_terms: set[str],
    recommended_size: str | None,
    alternative_size: str | None,
) -> tuple[float, list[str]]:
    score = 0.0
    score_parts = []

    if has_stock(candidate):
        score += 0.35

    if recommended_size or alternative_size:
        match_type = candidate_size_match_type(candidate, recommended_size, alternative_size)
        if match_type == "primary":
            score += 0.4
        elif match_type == "alternative":
            score += 0.25
        else:
            return -1.0, []

    match_score = term_match_score(query_terms, candidate)
    if match_score:
        score += match_score * 0.2
        score_parts.append("风格或场景标签匹配")

    sale_price = as_number(candidate.get("sale_price"))
    if sale_price is not None:
        score += 0.05

    return score, score_parts


def build_product_refs(
    candidates: list[dict[str, Any]] | None,
    intent_result: dict[str, Any] | None,
    user_query: str,
    user_context: dict[str, Any] | None,
    tool_results: dict[str, Any] | None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Select refs only from Java candidates; never invent product facts."""
    if not candidates:
        return []

    intent = (intent_result or {}).get("intent")
    if intent not in RECOMMENDABLE_INTENTS:
        return []

    user_context = user_context or {}
    tool_results = tool_results or {}
    recommended_size = get_recommended_size(tool_results)
    alternative_size = get_alternative_size(tool_results)
    query_terms = collect_query_terms(user_query, user_context)

    scored_candidates = []
    seen_skus = set()

    for index, candidate in enumerate(candidates):
        sku_id = candidate.get("sku_id")
        spu_id = candidate.get("spu_id")
        if sku_id is None or spu_id is None or sku_id in seen_skus:
            continue

        score, score_parts = score_candidate(candidate, query_terms, recommended_size, alternative_size)
        if score < 0:
            continue

        seen_skus.add(sku_id)
        scored_candidates.append((score, index, candidate, score_parts))

    scored_candidates.sort(key=lambda item: (-item[0], item[1]))
    refs = []

    for score, _, candidate, score_parts in scored_candidates[:limit]:
        refs.append(
            {
                "spu_id": candidate["spu_id"],
                "sku_id": candidate["sku_id"],
                "reason": build_reason(candidate, recommended_size, alternative_size, score_parts),
                "rank_score": round(score, 4),
            }
        )

    return refs
