"""Deterministic product reference selection for Java-provided candidates."""

from typing import Any

from clothing_assistant.agent.router import (
    INTENT_PRODUCT_QA,
    INTENT_RECOMMENDATION,
    INTENT_SIZE_RECOMMENDATION,
)
from clothing_assistant.application.preference_parser import (
    append_unique,
    build_empty_preferences,
    merge_preferences,
    parse_preferences,
)


RECOMMENDABLE_INTENTS = {
    INTENT_PRODUCT_QA,
    INTENT_RECOMMENDATION,
    INTENT_SIZE_RECOMMENDATION,
}

IN_STOCK_STATUSES = {"in_stock", "low_stock", "available", "on_sale"}

VISUAL_GOAL_TERMS = {
    "taller": ["taller", "显高", "高腰", "中高腰", "短款", "直筒", "拉长比例", "显腿长"],
    "slimmer": ["slimmer", "显瘦", "修身", "直筒", "垂顺", "深色", "黑色", "藏青色", "遮肉"],
}

VISUAL_GOAL_REASONS = {
    "taller": "版型或腰线更利于拉长比例",
    "slimmer": "颜色、线条或版型更贴合显瘦需求",
}

AVOID_TAG_TERMS = {
    "bulky": ["bulky", "臃肿", "厚重", "膨胀", "拖沓"],
    "low_waist": ["low_waist", "低腰"],
    "overly_formal": ["overly_formal", "过度正式", "商务正装", "正式商务"],
    "oversized": ["oversized", "过度宽松", "超宽松", "oversize"],
}

QUERY_TERM_ALIASES = [
    (["裙子", "半裙", "半身裙", "百褶裙", "A字裙", "a字裙", "直筒裙"], ["裙", "半裙"]),
]
WARM_MATCH_TERMS = ["warm", "保暖", "厚款", "厚实", "羊毛", "羽绒", "加绒", "针织"]
RAG_FACT_FORBIDDEN_TERMS = ["sku", "价格", "库存", "有货", "无货", "下架", "上架", "元"]
REJECTION_HARD_FILTER = "HARD_FILTER_MISMATCH"
REJECTION_SIZE = "SIZE_MISMATCH"
REJECTION_LOW_STYLE = "LOW_STYLE_SCORE"
REJECTION_MISSING_EVIDENCE = "MISSING_REQUIRED_EVIDENCE"


def normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def normalize_size(value: Any) -> str:
    return str(value or "").strip().upper()


def normalize_identifier(value: Any) -> str:
    return str(value).strip() if value is not None else ""


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


def collect_query_terms(user_query: str, user_context: dict[str, Any], preferences: dict[str, Any]) -> set[str]:
    terms = set()
    normalized_query = normalize_text(user_query)

    for value in [
        "面试",
        "通勤",
        "日常",
        "显瘦",
        "宽松",
        "修身",
        "外套",
        "夹克",
        "T恤",
        "衬衫",
        "卫衣",
        "裤子",
        "西装",
        "半裙",
        "短裤",
        "夏",
        "冬",
        "春",
        "秋",
    ]:
        if value.lower() in normalized_query:
            terms.add(value.lower())

    for signals, mapped_terms in QUERY_TERM_ALIASES:
        if any(normalize_text(signal) in normalized_query for signal in signals):
            terms.update(normalize_text(term) for term in mapped_terms)

    for key in ["preferred_styles", "preferred_colors", "preferred_categories"]:
        values = user_context.get(key) or []
        for value in values:
            if value:
                terms.add(normalize_text(value))

    for key in ["scene", "style_tags", "visual_goals", "persona_tags", "season"]:
        for value in preferences.get(key) or []:
            terms.add(normalize_text(value))

    return terms


def iterable_candidate_values(value: Any) -> list[Any]:
    if value is None:
        return []

    if isinstance(value, (list, tuple, set)):
        return list(value)

    return [value]


def candidate_terms(candidate: dict[str, Any]) -> set[str]:
    terms = set()

    for key in ["name", "category", "category_name", "color", "material", "materials", "fit_type"]:
        value = normalize_text(candidate.get(key))
        if value:
            terms.add(value)

    for key in ["season", "seasons", "style_tags", "attribute_tags", "visual_effect_tags", "occasion_tags"]:
        for value in iterable_candidate_values(candidate.get(key)):
            normalized = normalize_text(value)
            if normalized:
                terms.add(normalized)

    return terms


def candidate_text(candidate: dict[str, Any]) -> str:
    return " ".join(candidate_terms(candidate))


def normalized_values(value: Any) -> list[str]:
    return [normalized for item in iterable_candidate_values(value) if (normalized := normalize_text(item))]


def v3_constraint_values(
    demand_intent: dict[str, Any],
    field: str,
    collections: tuple[str, ...] = ("hardFilters", "softPreferences"),
) -> list[Any] | None:
    """Return values from selected v3 partitions, or None when they do not declare the field."""
    if normalize_text(demand_intent.get("version")) != "demand-intent-v3":
        return None

    values = []
    found = False
    for collection in collections:
        for constraint in demand_intent.get(collection) or []:
            if not isinstance(constraint, dict) or constraint.get("field") != field:
                continue
            found = True
            values.extend(iterable_candidate_values(constraint.get("values")))
    return values if found else None


def preference_values(
    demand_intent: dict[str, Any],
    field: str,
    *legacy_keys: str,
) -> list[str]:
    """Read only soft v3 constraints for ranking, without reusing hard values as preferences."""
    soft_values = v3_constraint_values(demand_intent, field, ("softPreferences",))
    if soft_values is not None:
        return normalized_values(soft_values)
    if v3_constraint_values(demand_intent, field, ("hardFilters",)) is not None:
        return []
    return demand_values(demand_intent, field, *(legacy_keys or (field,)))


def hard_constraint_values(demand_intent: dict[str, Any], field: str) -> list[str]:
    return normalized_values(
        v3_constraint_values(demand_intent, field, ("hardFilters",)) or []
    )


def demand_values(
    demand_intent: dict[str, Any],
    field: str,
    *legacy_keys: str,
) -> list[str]:
    """Read v3 constraints first, falling back to legacy scalar extras only when absent."""
    constraint_values = v3_constraint_values(demand_intent, field)
    if constraint_values is not None:
        raw_values = constraint_values
    else:
        raw_values = []
        for key in legacy_keys or (field,):
            value = demand_intent.get(key)
            if value is not None:
                raw_values.extend(iterable_candidate_values(value))

    result = []
    for value in normalized_values(raw_values):
        if value not in result:
            result.append(value)
    return result


def demand_budget_max(demand_intent: dict[str, Any]) -> float | None:
    if normalize_text(demand_intent.get("version")) == "demand-intent-v3":
        hard_values = v3_constraint_values(demand_intent, "budgetMax", ("hardFilters",))
        values = (
            hard_values
            if hard_values is not None
            else v3_constraint_values(demand_intent, "budgetMax", ("softPreferences",))
        )
    else:
        values = None
    if values is not None:
        numeric_values = [number for value in values if (number := as_number(value)) is not None]
        return min(numeric_values) if numeric_values else None
    return as_number(demand_intent.get("budgetMax") or demand_intent.get("budget_max"))


def hard_budget_max(demand_intent: dict[str, Any]) -> float | None:
    if normalize_text(demand_intent.get("version")) == "demand-intent-v3":
        values = v3_constraint_values(demand_intent, "budgetMax", ("hardFilters",)) or []
        numeric_values = [number for value in values if (number := as_number(value)) is not None]
        return min(numeric_values) if numeric_values else None
    return as_number(demand_intent.get("budgetMax") or demand_intent.get("budget_max"))


def preference_budget_max(demand_intent: dict[str, Any]) -> float | None:
    if normalize_text(demand_intent.get("version")) == "demand-intent-v3":
        values = v3_constraint_values(demand_intent, "budgetMax", ("softPreferences",))
        if values is not None:
            numeric_values = [number for value in values if (number := as_number(value)) is not None]
            return min(numeric_values) if numeric_values else None
        if v3_constraint_values(demand_intent, "budgetMax", ("hardFilters",)) is not None:
            return None
    return as_number(demand_intent.get("budgetMax") or demand_intent.get("budget_max"))


def candidate_fails_hard_constraints(
    candidate: dict[str, Any],
    demand_intent: dict[str, Any] | None,
) -> bool:
    """Apply only candidate-verifiable HARD conditions; Java remains authoritative for other facts."""
    if not isinstance(demand_intent, dict):
        return False

    budget_max = hard_budget_max(demand_intent)
    candidate_price = as_number(candidate.get("sale_price"))
    if budget_max is not None and (candidate_price is None or candidate_price > budget_max):
        return True

    scalar_fields = {
        "category": normalize_text(candidate.get("category") or candidate.get("category_name")),
        "fitPreferences": normalize_text(candidate.get("fit_type")),
    }
    for field, candidate_value in scalar_fields.items():
        requested = hard_constraint_values(demand_intent, field)
        if requested and candidate_value not in requested:
            return True

    collection_fields = {
        "season": normalized_values(candidate.get("season")) + normalized_values(candidate.get("seasons")),
        "style": normalized_values(candidate.get("style_tags")) + candidate_tag_values(candidate, "attribute_tags"),
        "attributes": candidate_tag_values(candidate, "attribute_tags"),
    }
    for field, candidate_values in collection_fields.items():
        requested = hard_constraint_values(demand_intent, field)
        if requested and not set(requested) & set(candidate_values):
            return True
    return False


def candidate_tag_values(candidate: dict[str, Any], key: str) -> list[str]:
    """Return Java-verifiable tag values, stripping an optional `name:` prefix."""
    values = []
    for raw_value in iterable_candidate_values(candidate.get(key)):
        value = normalize_text(raw_value)
        if not value:
            continue
        values.append(value.split(":", 1)[1].strip() if ":" in value else value)
    return values


def append_match(
    matches: list[dict[str, str]],
    dimension: str,
    requested_value: Any,
    candidate_value: Any,
    evidence_source: str,
) -> None:
    requested = normalize_text(requested_value)
    candidate = normalize_text(candidate_value)
    if not requested or not candidate:
        return
    matches.append(
        {
            "dimension": dimension,
            "requested_value": requested,
            "candidate_value": candidate,
            "evidence_source": evidence_source,
        }
    )


def query_fallback_demand(
    user_query: str,
    candidate: dict[str, Any],
    preferences: dict[str, Any],
) -> dict[str, Any]:
    """Build conservative v1/no-contract evidence only from explicit query text."""
    query = normalize_text(user_query)
    category = normalize_text(candidate.get("category") or candidate.get("category_name"))
    season = None
    for terms, code in [
        (("春天", "春季"), "spring"),
        (("夏天", "夏季"), "summer"),
        (("秋天", "秋季", "秋冬"), "autumn"),
        (("冬天", "冬季", "秋冬"), "winter"),
    ]:
        if any(term in query for term in terms):
            season = code
            break

    styles = []
    for terms, code in [
        (("休闲", "轻松"), "casual"),
        (("简约", "极简"), "minimal"),
        (("正式", "商务"), "formal"),
    ]:
        if any(term in query for term in terms):
            styles.append(code)

    fits = []
    if "宽松" in query or "轻松一点" in query:
        fits.append("relaxed")
    if "修身" in query:
        fits.append("slim")

    return {
        "category": category if category and category in query else None,
        "season": season,
        "style": styles,
        "fitPreferences": fits,
        "attributes": [value for value in candidate_tag_values(candidate, "attribute_tags") if value in query],
        "budgetMax": preferences.get("budget_max"),
    }


def build_matched_dimensions(
    candidate: dict[str, Any],
    demand_intent: dict[str, Any] | None,
    user_query: str,
    preferences: dict[str, Any],
) -> list[dict[str, str]]:
    """Build only structured facts that Java can independently verify."""
    demand = demand_intent if isinstance(demand_intent, dict) and demand_intent else query_fallback_demand(
        user_query, candidate, preferences
    )
    matches: list[dict[str, str]] = []

    requested_categories = demand_values(demand, "category")
    candidate_category = normalize_text(candidate.get("category") or candidate.get("category_name"))
    if candidate_category in requested_categories:
        append_match(matches, "category", candidate_category, candidate_category, "PRODUCT_CATEGORY")

    requested_seasons = demand_values(demand, "season")
    candidate_seasons = normalized_values(candidate.get("season")) + normalized_values(candidate.get("seasons"))
    for requested_season in requested_seasons:
        if requested_season in candidate_seasons:
            append_match(matches, "season", requested_season, requested_season, "PRODUCT_SEASON")

    candidate_styles = normalized_values(candidate.get("style_tags")) + candidate_tag_values(
        candidate, "attribute_tags"
    )
    for requested_style in demand_values(demand, "style"):
        if requested_style in candidate_styles:
            append_match(matches, "style", requested_style, requested_style, "PRODUCT_STYLE_TAG")

    candidate_fit = normalize_text(candidate.get("fit_type"))
    for requested_fit in demand_values(demand, "fitPreferences", "fitPreferences", "fit_preferences"):
        if requested_fit == candidate_fit:
            append_match(matches, "fitPreferences", requested_fit, candidate_fit, "PRODUCT_FIT")

    candidate_attributes = candidate_tag_values(candidate, "attribute_tags")
    for requested_attribute in demand_values(demand, "attributes"):
        if requested_attribute in candidate_attributes:
            append_match(
                matches,
                "attributes",
                requested_attribute,
                requested_attribute,
                "PRODUCT_ATTRIBUTE",
            )

    requested_budget = demand_budget_max(demand)
    candidate_price = as_number(candidate.get("sale_price"))
    if requested_budget is not None and candidate_price is not None and candidate_price <= requested_budget:
        append_match(
            matches,
            "budgetMax",
            format_amount(requested_budget),
            format_amount(candidate_price),
            "PRODUCT_PRICE",
        )

    return matches


def is_winter_warm_query(preferences: dict[str, Any]) -> bool:
    return "warm" in (preferences.get("style_tags") or []) or "winter" in (preferences.get("season") or [])


def candidate_has_winter_season(candidate: dict[str, Any]) -> bool:
    season_values = iterable_candidate_values(candidate.get("season")) + iterable_candidate_values(candidate.get("seasons"))
    return any(normalize_text(value) == "winter" for value in season_values)


def candidate_has_warm_signal(candidate: dict[str, Any]) -> bool:
    text = candidate_text(candidate)
    return any(term in text for term in WARM_MATCH_TERMS)


def preferences_from_demand_intent(demand_intent: dict[str, Any] | None) -> dict[str, Any]:
    """Map Java's safe intent contract onto existing rerank preference keys."""
    preferences = build_empty_preferences()
    if not isinstance(demand_intent, dict):
        return preferences

    append_unique(preferences["scene"], preference_values(demand_intent, "scene"))
    append_unique(preferences["style_tags"], preference_values(demand_intent, "style"))
    append_unique(preferences["season"], preference_values(demand_intent, "season"))

    attributes = set(preference_values(demand_intent, "attributes"))
    if {"保暖", "厚款"} & attributes:
        append_unique(preferences["style_tags"], ["warm"])
        append_unique(preferences["season"], ["winter"])
    if "平价" in attributes:
        preferences["price_preference"] = "budget"
    if "显瘦" in attributes:
        append_unique(preferences["visual_goals"], ["slimmer"])
    if "显高" in attributes:
        append_unique(preferences["visual_goals"], ["taller"])

    budget_max = preference_budget_max(demand_intent)
    if budget_max is not None:
        preferences["budget_max"] = int(budget_max)

    return preferences


def resolve_preferences(user_query: str, demand_intent: dict[str, Any] | None = None) -> dict[str, Any]:
    return merge_preferences(parse_preferences(user_query), preferences_from_demand_intent(demand_intent))


def collect_preferred_colors(user_context: dict[str, Any], preferences: dict[str, Any]) -> set[str]:
    colors = {normalize_text(value) for value in user_context.get("preferred_colors") or [] if value}
    colors.update(normalize_text(value) for value in preferences.get("preferred_colors") or [] if value)
    return colors


def collect_context_ids(user_context: dict[str, Any], key: str) -> set[str]:
    return {normalize_identifier(value) for value in user_context.get(key) or [] if normalize_identifier(value)}


def collect_context_terms(user_context: dict[str, Any], key: str) -> set[str]:
    return {normalize_text(value) for value in user_context.get(key) or [] if normalize_text(value)}


def resolve_budget_max(user_context: dict[str, Any], preferences: dict[str, Any]) -> float | None:
    context_budget = as_number(user_context.get("budget_max"))
    preference_budget = as_number(preferences.get("budget_max"))
    return context_budget if context_budget is not None else preference_budget


def term_match_score(query_terms: set[str], candidate: dict[str, Any]) -> float:
    if not query_terms:
        return 0

    text = candidate_text(candidate)
    matched = sum(1 for term in query_terms if term and term in text)
    return matched / len(query_terms)


def has_term_match(query_terms: set[str], candidate: dict[str, Any]) -> bool:
    if not query_terms:
        return False

    text = candidate_text(candidate)
    return any(term and term in text for term in query_terms)


def format_amount(value: float) -> str:
    if value.is_integer():
        return str(int(value))

    return f"{value:.2f}".rstrip("0").rstrip(".")


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
    rag_explanation_parts: list[str] | None = None,
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
    details.extend(rag_explanation_parts or [])

    if not details:
        details.append("符合本轮 Java 候选商品条件")

    return f"{name}：" + "，".join(details) + "。"


def summarize_rag_content(content: str, max_length: int = 48) -> str:
    summary = " ".join(str(content or "").split())
    if len(summary) <= max_length:
        return summary

    return summary[:max_length].rstrip("，。,. ") + "..."


def extract_rag_explanation_parts(tool_results: dict[str, Any]) -> list[str]:
    rag_result = tool_results.get("rag_tool") or {}
    chunks = rag_result.get("retrieved_chunks") or []
    explanation_parts = []

    for chunk in chunks:
        content = str(chunk.get("content") or "")
        normalized = normalize_text(content)
        if not content.strip():
            continue
        if any(term in normalized for term in RAG_FACT_FORBIDDEN_TERMS):
            continue
        explanation_parts.append(f"RAG 知识提示：{summarize_rag_content(content)}")
        break

    return explanation_parts


def behavior_context_score(candidate: dict[str, Any], user_context: dict[str, Any], score_parts: list[str]) -> float:
    score = 0.0
    candidate_spu_id = normalize_identifier(candidate.get("spu_id"))

    if candidate_spu_id and candidate_spu_id in collect_context_ids(user_context, "recent_interest_spu_ids"):
        score += 0.12
        score_parts.append("近期行为显示你关注过类似商品")

    if candidate_spu_id and candidate_spu_id in collect_context_ids(user_context, "recent_cart_spu_ids"):
        score += 0.16
        score_parts.append("你近期有类似加购意图")

    if candidate_spu_id and candidate_spu_id in collect_context_ids(user_context, "recent_purchased_spu_ids"):
        score += 0.08
        score_parts.append("与你近期购买偏好相近")

    candidate_category = normalize_text(candidate.get("category") or candidate.get("category_name"))
    if candidate_category and candidate_category in collect_context_terms(user_context, "behavior_preferred_categories"):
        score += 0.08
        score_parts.append("匹配近期浏览或购买分类")

    preferred_styles = collect_context_terms(user_context, "behavior_preferred_styles")
    candidate_styles = {normalize_text(value) for value in candidate.get("style_tags") or [] if value}
    if preferred_styles and candidate_styles & preferred_styles:
        score += 0.08
        score_parts.append("匹配近期偏好的风格")

    return score


def score_candidate(
    candidate: dict[str, Any],
    query_terms: set[str],
    recommended_size: str | None,
    alternative_size: str | None,
    user_context: dict[str, Any],
    preferences: dict[str, Any],
    enforce_preference_limits: bool = True,
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

    if has_term_match(query_terms, candidate):
        match_score = term_match_score(query_terms, candidate)
        score += match_score * 0.2
        score_parts.append("风格、季节或场景标签匹配")

    sale_price = as_number(candidate.get("sale_price"))
    budget_max = resolve_budget_max(user_context, preferences)
    if (
        enforce_preference_limits
        and sale_price is not None
        and budget_max is not None
        and sale_price > budget_max
    ):
        return -1.0, []

    if sale_price is not None and budget_max is not None and sale_price <= budget_max:
        score += 0.1
        score_parts.append(f"价格 {format_amount(sale_price)} 在预算 {format_amount(budget_max)} 内")
    elif sale_price is not None:
        score += 0.05

    if sale_price is not None and preferences.get("price_preference") == "budget":
        score += 0.1
        score_parts.append("符合平价优先")

    preferred_colors = collect_preferred_colors(user_context, preferences)
    candidate_color = normalize_text(candidate.get("color"))
    if candidate_color and candidate_color in preferred_colors:
        score += 0.1
        score_parts.append(f"{candidate.get('color')}匹配颜色偏好")

    score += behavior_context_score(candidate, user_context, score_parts)

    text = candidate_text(candidate)

    if is_winter_warm_query(preferences):
        winter_match = candidate_has_winter_season(candidate)
        warm_match = candidate_has_warm_signal(candidate)
        if enforce_preference_limits and not winter_match and not warm_match:
            return -1.0, []
        if winter_match:
            score += 0.3
            score_parts.append("匹配冬季需求")
        if warm_match:
            score += 0.35
            score_parts.append("材质或厚度更适合保暖")

    if preferences.get("visual_goals"):
        for goal in preferences["visual_goals"]:
            terms = VISUAL_GOAL_TERMS.get(goal, [normalize_text(goal)])
            if any(term in text for term in terms):
                score += 0.08
                score_parts.append(VISUAL_GOAL_REASONS.get(goal, "匹配视觉修饰目标"))

    if "student" in (preferences.get("persona_tags") or []):
        if preferences.get("price_preference") == "budget" and sale_price is not None:
            score += 0.06
            score_parts.append("价格和风格更适合学生日常穿搭")
        if any(term in text for term in ["campus", "daily", "casual", "basic", "校园", "日常", "休闲", "基础"]):
            score += 0.06
            score_parts.append("偏休闲基础，适合校园或日常场景")

    if {"basic", "minimal"} & set(preferences.get("style_tags") or []):
        if any(term in text for term in ["basic", "minimal", "基础", "简洁", "百搭"]):
            score += 0.06
            score_parts.append("基础色或简洁版型更容易一衣多穿")

    # avoid_tags is a soft penalty: demote risky items without emptying a small
    # Java candidate pool just because one non-ideal feature is present.
    for avoid_tag in preferences.get("avoid_tags") or []:
        risky_terms = AVOID_TAG_TERMS.get(avoid_tag, [normalize_text(avoid_tag)])
        if any(term in text for term in risky_terms):
            score -= 0.08
            score_parts.append("存在部分需要规避的版型或风格特征")

    return score, score_parts


def build_product_refs(
    candidates: list[dict[str, Any]] | None,
    intent_result: dict[str, Any] | None,
    user_query: str,
    user_context: dict[str, Any] | None,
    tool_results: dict[str, Any] | None,
    limit: int = 3,
    demand_intent: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Select refs only from Java candidates; never invent product facts."""
    return build_product_rerank_result(
        candidates,
        intent_result,
        user_query,
        user_context,
        tool_results,
        limit=limit,
        demand_intent=demand_intent,
    )["product_refs"]


def build_product_rerank_result(
    candidates: list[dict[str, Any]] | None,
    intent_result: dict[str, Any] | None,
    user_query: str,
    user_context: dict[str, Any] | None,
    tool_results: dict[str, Any] | None,
    limit: int = 3,
    demand_intent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Rank Java-provided candidates and expose debug evidence for the AI layer."""
    preferences = resolve_preferences(user_query, demand_intent)
    if not candidates:
        return {
            "product_refs": [],
            "semantic_preferences": preferences,
            "candidate_scores": [],
            "recommendation_source": "java_candidates_empty",
            "rejected_reasons": {},
        }

    intent = (intent_result or {}).get("intent")
    if intent not in RECOMMENDABLE_INTENTS:
        return {
            "product_refs": [],
            "semantic_preferences": preferences,
            "candidate_scores": [],
            "recommendation_source": "not_recommendable_intent",
            "rejected_reasons": {},
        }

    user_context = user_context or {}
    tool_results = tool_results or {}
    recommended_size = get_recommended_size(tool_results)
    alternative_size = get_alternative_size(tool_results)
    query_terms = collect_query_terms(user_query, user_context, preferences)
    rag_explanation_parts = extract_rag_explanation_parts(tool_results)
    enforce_preference_limits = normalize_text((demand_intent or {}).get("version")) != "demand-intent-v3"

    scored_candidates = []
    candidate_scores = []
    seen_skus = set()

    for index, candidate in enumerate(candidates):
        sku_id = candidate.get("sku_id")
        spu_id = candidate.get("spu_id")
        if sku_id is None or spu_id is None or sku_id in seen_skus:
            continue

        matched_dimensions = build_matched_dimensions(
            candidate,
            demand_intent,
            user_query,
            preferences,
        )
        if candidate_fails_hard_constraints(candidate, demand_intent):
            score, score_parts = -1.0, []
            rejection_reason = REJECTION_HARD_FILTER
        else:
            score, score_parts = score_candidate(
                candidate,
                query_terms,
                recommended_size,
                alternative_size,
                user_context,
                preferences,
                enforce_preference_limits=enforce_preference_limits,
            )
            if score < 0 and not candidate_matches_size(
                candidate,
                recommended_size,
                alternative_size,
            ):
                rejection_reason = REJECTION_SIZE
            elif score < 0:
                rejection_reason = REJECTION_LOW_STYLE
            elif not matched_dimensions:
                rejection_reason = REJECTION_MISSING_EVIDENCE
            else:
                rejection_reason = None
        selected = rejection_reason is None

        candidate_scores.append(
            {
                "spu_id": spu_id,
                "sku_id": sku_id,
                "rank_score": round(score, 4),
                "selected": selected,
                "score_parts": score_parts,
                "matched_dimensions": matched_dimensions,
                "rejection_reason": rejection_reason,
            }
        )

        if selected:
            seen_skus.add(sku_id)
            scored_candidates.append((score, index, candidate, score_parts, matched_dimensions))

    scored_candidates.sort(key=lambda item: (-item[0], item[1]))
    candidate_scores.sort(key=lambda item: (-item["rank_score"], str(item["spu_id"]), str(item["sku_id"])))
    refs = []

    for score, _, candidate, score_parts, matched_dimensions in scored_candidates[:limit]:
        refs.append(
            {
                "spu_id": candidate["spu_id"],
                "sku_id": candidate["sku_id"],
                "reason": build_reason(
                    candidate,
                    recommended_size,
                    alternative_size,
                    score_parts,
                    rag_explanation_parts=rag_explanation_parts,
                ),
                "rank_score": round(score, 4),
                "matched_dimensions": matched_dimensions,
            }
        )

    selected_ref_keys = {(ref["spu_id"], ref["sku_id"]) for ref in refs}
    for candidate_score in candidate_scores:
        candidate_score["selected"] = (candidate_score["spu_id"], candidate_score["sku_id"]) in selected_ref_keys
        if not candidate_score["selected"] and candidate_score["rejection_reason"] is None:
            candidate_score["rejection_reason"] = REJECTION_LOW_STYLE

    rejected_reasons = {}
    for candidate_score in candidate_scores:
        reason = candidate_score["rejection_reason"]
        if reason:
            rejected_reasons[reason] = rejected_reasons.get(reason, 0) + 1

    return {
        "product_refs": refs,
        "semantic_preferences": preferences,
        "candidate_scores": candidate_scores,
        "recommendation_source": "java_candidates_with_ai_rerank",
        "rejected_reasons": rejected_reasons,
    }
