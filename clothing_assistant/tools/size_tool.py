import re

from clothing_assistant.size_matcher import has_complete_measurements, match_size_rule


RELAXED_PREFERENCE_KEYWORDS = ["宽松", "松一点", "大一点", "oversize", "宽大"]
FIT_PREFERENCE_KEYWORDS = ["合身", "正常", "标准"]
TIGHT_PREFERENCE_KEYWORDS = ["偏紧", "修身", "紧一点", "贴身"]

SIZE_ORDER = ["S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL"]


def contains_any(text, keywords):
    return any(keyword in text for keyword in keywords)


def extract_size_preference(user_query):
    """从用户问题里识别简单穿着偏好。"""
    normalized_query = user_query.strip().lower()

    if contains_any(normalized_query, RELAXED_PREFERENCE_KEYWORDS):
        return "relaxed"

    if contains_any(normalized_query, TIGHT_PREFERENCE_KEYWORDS):
        return "tight"

    if contains_any(normalized_query, FIT_PREFERENCE_KEYWORDS):
        return "regular"

    return None


def normalize_measurement_query(user_query):
    """把“175cm 70kg”这类省略写法补成底层规则模块能识别的表达。"""
    normalized_query = user_query

    if "身高" not in normalized_query:
        height_match = re.search(r"(\d{2,3})\s*(cm|厘米)", normalized_query, re.IGNORECASE)

        if height_match:
            normalized_query = (
                f"{normalized_query[:height_match.start()]}"
                f"身高{height_match.group(1)}cm"
                f"{normalized_query[height_match.end():]}"
            )

    if "体重" not in normalized_query:
        weight_match = re.search(r"(\d{2,3})\s*(kg|公斤|斤)", normalized_query, re.IGNORECASE)

        if weight_match:
            normalized_query = (
                f"{normalized_query[:weight_match.start()]}"
                f"体重{weight_match.group(1)}{weight_match.group(2)}"
                f"{normalized_query[weight_match.end():]}"
            )

    return normalized_query


def get_next_size(size):
    if size not in SIZE_ORDER:
        return None

    current_index = SIZE_ORDER.index(size)

    if current_index >= len(SIZE_ORDER) - 1:
        return None

    return SIZE_ORDER[current_index + 1]


def find_latest_history_user_query_with_measurements(chat_history):
    if not chat_history:
        return None

    # 只从历史里的用户问题找身高体重，避免助手回答里的尺码规则污染当前工具输入。
    for chat_turn in reversed(chat_history):
        history_query = chat_turn.get("user_query", "").strip()

        if history_query and has_complete_measurements(history_query):
            return history_query

    return None


def build_size_query(user_query, chat_history=None):
    normalized_user_query = normalize_measurement_query(user_query)

    if has_complete_measurements(normalized_user_query):
        return normalized_user_query

    history_query = find_latest_history_user_query_with_measurements(chat_history)

    if not history_query:
        return normalized_user_query

    # 当前问题缺少身高体重时，才用最近一轮用户问题补上下文。
    return f"{history_query}\n当前追问：{normalized_user_query}"


def build_size_tool_result(size_match, size_query, preference):
    recommended_size = size_match["primary_size"]
    alternative = size_match["alternative_size"]
    reason = size_match["reason"]

    if preference == "relaxed" and recommended_size:
        relaxed_size = get_next_size(recommended_size)

        if relaxed_size:
            alternative = relaxed_size
            reason = f"{reason} 用户偏好宽松，可在主推荐尺码基础上考虑加大一码。"

    if preference == "tight" and recommended_size:
        reason = f"{reason} 用户偏好修身，建议优先试穿主推荐尺码，避免盲目加大。"

    return {
        "recommended_size": recommended_size,
        "reason": reason,
        "alternative": alternative,
        "match_type": size_match["match_type"],
        "preference": preference,
        "size_query": size_query,
        "measurements": size_match["measurements"],
        "raw_match": size_match,
    }


def run_size_tool(user_query, chat_history=None):
    """Agent 尺码工具入口：构造干净尺码输入，再调用现有规则匹配能力。"""
    size_query = build_size_query(user_query, chat_history)
    preference = extract_size_preference(user_query)
    size_match = match_size_rule(size_query)

    return build_size_tool_result(size_match, size_query, preference)


def main():
    test_history = [
        {
            "user_query": "我身高168，体重65kg，想买一件日常穿的T恤",
            "assistant_answer": "推荐 L 码",
        }
    ]
    test_queries = [
        ("我 175cm 70kg 穿什么码？", []),
        ("那我想宽松一点呢？", test_history),
    ]

    for query, history in test_queries:
        print(query)
        print(run_size_tool(query, chat_history=history))
        print("-" * 60)


if __name__ == "__main__":
    main()
