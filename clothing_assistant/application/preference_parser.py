"""Map fuzzy shopping language into structured recommendation preferences.

The parser intentionally produces preferences only. Product identity, price,
stock, and SKU facts still have to come from Java-provided candidates.
"""

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from clothing_assistant.config_data import ENABLE_LLM_PREFERENCE_MAPPER
from clothing_assistant.infrastructure.llm_client import get_chat_model


logger = logging.getLogger(__name__)

LLM_CONFIDENCE_THRESHOLD = 0.55


ALLOWED_VALUES = {
    "scene": {"commute", "date", "campus", "daily", "travel", "sport"},
    "persona_tags": {"student"},
    "visual_goals": {"taller", "slimmer"},
    "style_tags": {"commute", "minimal", "casual", "basic", "date", "warm", "sport"},
    "preferred_colors": {"黑色", "白色", "灰色", "藏青色", "深蓝色", "米色"},
    "avoid_tags": {"bulky", "low_waist", "overly_formal", "oversized"},
    "season": {"spring", "summer", "autumn", "winter"},
}

# These signal groups are the deterministic fallback for fuzzy portraits.
# They intentionally map many user expressions into a small, safe tag set.
STUDENT_SIGNALS = [
    "学生党",
    "学生",
    "大学生",
    "校园",
    "上课",
    "上学",
    "宿舍",
    "社团",
    "年轻一点",
    "别太成熟",
    "日常上课",
]

SLIMMER_SIGNALS = [
    "显瘦",
    "遮肉",
    "藏肉",
    "不显胖",
    "修饰身材",
    "梨形",
    "微胖",
    "腿粗",
    "胯宽",
    "肚子",
    "肉肉",
]

TALLER_SIGNALS = [
    "显高",
    "小个子",
    "拉长比例",
    "显腿长",
    "比例好",
    "腿短",
    "不压个子",
    "精神一点",
]

BUDGET_SIGNALS = [
    "平价",
    "便宜",
    "不贵",
    "性价比",
    "预算有限",
    "学生预算",
    "别太贵",
    "划算",
    "入门款",
]

VERSATILE_SIGNALS = [
    "百搭",
    "好搭",
    "一衣多穿",
    "通用",
    "日常都能穿",
    "不挑场合",
    "基础款",
    "耐看",
]

COMMUTE_SIGNALS = ["通勤", "上班", "办公室", "职场", "上班穿", "上班通勤"]
DATE_SIGNALS = ["约会", "见面", "见男朋友", "见女朋友", "约会穿搭"]
WARM_SIGNALS = ["保暖", "怕冷", "厚实", "秋冬保暖", "暖和"]
NOT_TOO_FORMAL_SIGNALS = ["不要太正式", "别太正式", "不想太成熟", "不要太成熟", "不商务", "别商务"]

SEASON_SIGNALS = [
    (["春", "春天", "春季"], "spring"),
    (["夏", "夏天", "夏季"], "summer"),
    (["秋", "秋天", "秋季"], "autumn"),
    (["冬", "冬天", "冬季"], "winter"),
]


def normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def append_unique(values: list[Any], new_values: list[Any]) -> None:
    for value in new_values:
        if value and value not in values:
            values.append(value)


def contains_any_signal(normalized_text: str, signals: list[str]) -> bool:
    return any(normalize_text(signal) in normalized_text for signal in signals)


def parse_budget_max(user_query: str) -> int | None:
    patterns = [
        r"预算\s*(\d{2,5})\s*(以内|以下|内)?",
        r"(\d{2,5})\s*(以内|以下|内)",
        r"不超过\s*(\d{2,5})",
    ]

    for pattern in patterns:
        match = re.search(pattern, user_query)
        if match:
            value = next((group for group in match.groups() if group and group.isdigit()), None)
            if value:
                return int(value)

    return None


def build_empty_preferences() -> dict[str, Any]:
    return {
        "scene": [],
        "persona_tags": [],
        "visual_goals": [],
        "style_tags": [],
        "preferred_colors": [],
        "avoid_tags": [],
        "season": [],
        "price_preference": None,
        "budget_max": None,
        "confidence": 0.0,
        "missing_slots": [],
    }


def parse_rule_preferences(user_query: str) -> dict[str, Any]:
    normalized = normalize_text(user_query)
    preferences = build_empty_preferences()
    matched_signals = 0

    if contains_any_signal(normalized, STUDENT_SIGNALS):
        append_unique(preferences["persona_tags"], ["student"])
        append_unique(preferences["scene"], ["campus", "daily"])
        append_unique(preferences["style_tags"], ["casual", "basic"])
        preferences["price_preference"] = "budget"
        matched_signals += 1

    if contains_any_signal(normalized, TALLER_SIGNALS):
        append_unique(preferences["visual_goals"], ["taller"])
        append_unique(preferences["avoid_tags"], ["low_waist", "bulky"])
        append_unique(preferences["style_tags"], ["minimal"])
        matched_signals += 1

    if contains_any_signal(normalized, SLIMMER_SIGNALS):
        append_unique(preferences["visual_goals"], ["slimmer"])
        append_unique(preferences["preferred_colors"], ["黑色", "藏青色", "灰色"])
        append_unique(preferences["avoid_tags"], ["bulky", "oversized"])
        matched_signals += 1

    if contains_any_signal(normalized, BUDGET_SIGNALS):
        preferences["price_preference"] = "budget"
        append_unique(preferences["style_tags"], ["basic"])
        matched_signals += 1

    if contains_any_signal(normalized, VERSATILE_SIGNALS):
        append_unique(preferences["style_tags"], ["basic", "minimal"])
        append_unique(preferences["preferred_colors"], ["黑色", "白色", "灰色", "藏青色"])
        matched_signals += 1

    if contains_any_signal(normalized, COMMUTE_SIGNALS):
        append_unique(preferences["scene"], ["commute"])
        append_unique(preferences["style_tags"], ["commute", "minimal"])
        matched_signals += 1

    if contains_any_signal(normalized, DATE_SIGNALS):
        append_unique(preferences["scene"], ["date"])
        append_unique(preferences["style_tags"], ["date", "minimal"])
        matched_signals += 1

    if contains_any_signal(normalized, WARM_SIGNALS):
        append_unique(preferences["style_tags"], ["warm"])
        append_unique(preferences["season"], ["autumn", "winter"])
        matched_signals += 1

    if contains_any_signal(normalized, NOT_TOO_FORMAL_SIGNALS):
        append_unique(preferences["avoid_tags"], ["overly_formal"])
        append_unique(preferences["style_tags"], ["casual", "minimal"])
        matched_signals += 1

    for signals, season in SEASON_SIGNALS:
        if contains_any_signal(normalized, signals):
            append_unique(preferences["season"], [season])
            matched_signals += 1

    budget_max = parse_budget_max(user_query)
    if budget_max is not None:
        preferences["budget_max"] = budget_max
        preferences["price_preference"] = "budget"
        matched_signals += 1

    if matched_signals:
        preferences["confidence"] = min(0.95, 0.45 + matched_signals * 0.1)

    return preferences


def sanitize_llm_preferences(raw_mapping: str | dict[str, Any] | None) -> dict[str, Any]:
    if not raw_mapping:
        return build_empty_preferences()

    if isinstance(raw_mapping, str):
        try:
            mapping = json.loads(raw_mapping)
        except json.JSONDecodeError:
            return build_empty_preferences()
    elif isinstance(raw_mapping, dict):
        mapping = raw_mapping
    else:
        return build_empty_preferences()

    sanitized = build_empty_preferences()

    for key, allowed in ALLOWED_VALUES.items():
        values = mapping.get(key) or []
        if isinstance(values, str):
            values = [values]
        append_unique(sanitized[key], [value for value in values if value in allowed])

    budget_max = mapping.get("budget_max")
    if isinstance(budget_max, (int, float)) and budget_max >= 0:
        sanitized["budget_max"] = int(budget_max)

    price_preference = mapping.get("price_preference")
    if price_preference in {"budget", "balanced", "premium"}:
        sanitized["price_preference"] = price_preference

    confidence = mapping.get("confidence")
    if isinstance(confidence, (int, float)):
        sanitized["confidence"] = max(0.0, min(float(confidence), 1.0))

    missing_slots = mapping.get("missing_slots") or []
    if isinstance(missing_slots, list):
        sanitized["missing_slots"] = [str(value) for value in missing_slots if value]

    return sanitized


def merge_preferences(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = build_empty_preferences()

    for key in ALLOWED_VALUES:
        append_unique(merged[key], base.get(key, []))
        append_unique(merged[key], override.get(key, []))

    merged["budget_max"] = override.get("budget_max") if override.get("budget_max") is not None else base.get("budget_max")
    merged["price_preference"] = override.get("price_preference") or base.get("price_preference")
    merged["confidence"] = max(float(base.get("confidence") or 0.0), float(override.get("confidence") or 0.0))
    merged["missing_slots"] = list(dict.fromkeys((base.get("missing_slots") or []) + (override.get("missing_slots") or [])))
    return merged


def build_llm_mapper_prompt(user_query: str) -> str:
    return f"""
请把用户的服装导购需求解析成严格 JSON，不要输出解释文字。

用户需求：
{user_query}

只能使用以下字段：
- scene: commute/date/campus/daily/travel/sport 数组
- persona_tags: student 数组
- visual_goals: taller/slimmer 数组
- style_tags: commute/minimal/casual/basic/date/warm/sport 数组
- preferred_colors: 黑色/白色/灰色/藏青色/深蓝色/米色 数组
- avoid_tags: bulky/low_waist/overly_formal/oversized 数组
- season: spring/summer/autumn/winter 数组
- price_preference: budget/balanced/premium/null
- budget_max: 数字或 null
- confidence: 0 到 1
- missing_slots: 字符串数组

不要输出商品 ID、SKU、价格事实或库存事实。
""".strip()


def map_preferences_with_llm(user_query: str) -> dict[str, Any]:
    if not ENABLE_LLM_PREFERENCE_MAPPER:
        return build_empty_preferences()

    try:
        chat_model = get_chat_model()
        response = chat_model.invoke(
            [
                SystemMessage(content="你只做服装导购模糊需求到 JSON 偏好的映射。"),
                HumanMessage(content=build_llm_mapper_prompt(user_query)),
            ]
        )
    except Exception:
        logger.exception("LLM preference mapper failed")
        return build_empty_preferences()

    return sanitize_llm_preferences(response.content)


def parse_preferences(user_query: str, llm_mapping: str | dict[str, Any] | None = None) -> dict[str, Any]:
    """Return safe structured preferences from rules plus optional LLM JSON.

    The LLM is allowed to understand fuzzy language, but the result is still
    merged through the same allowlist. Product facts remain candidate-bound.
    """
    rule_preferences = parse_rule_preferences(user_query)
    llm_preferences = sanitize_llm_preferences(llm_mapping) if llm_mapping is not None else map_preferences_with_llm(user_query)

    # Low-confidence model output is not used for ranking. This keeps vague or
    # malformed semantic guesses from silently changing product order.
    if float(llm_preferences.get("confidence") or 0.0) < LLM_CONFIDENCE_THRESHOLD:
        return rule_preferences

    return merge_preferences(rule_preferences, llm_preferences)
