import re

from clothing_assistant.size_matcher import has_complete_measurements
from clothing_assistant.tools.size_tool import extract_size_preference


REFERENCE_WORDS = ["那", "这个", "这件", "刚才", "那个", "它", "还适合", "会不会", "我呢"]
PRODUCT_KEYWORDS = ["T恤", "外套", "裤子", "衬衫", "连衣裙", "短裤", "卫衣"]
SIZE_PATTERN = re.compile(r"\b(S|M|L|XL|2XL|3XL|4XL|5XL)\b", re.IGNORECASE)


def contains_any(text, keywords):
    return any(keyword in text for keyword in keywords)


def has_reference_words(user_query):
    return contains_any(user_query, REFERENCE_WORDS)


def extract_measurements_query(chat_history):
    if not chat_history:
        return None

    # 只看历史用户问题，不从助手回答抽身高体重，避免回答里的尺码规则污染。
    for chat_turn in reversed(chat_history):
        history_query = chat_turn.get("user_query", "").strip()

        if history_query and has_complete_measurements(history_query):
            return history_query

    return None


def extract_last_recommended_size(chat_history):
    if not chat_history:
        return None

    for chat_turn in reversed(chat_history):
        assistant_answer = chat_turn.get("assistant_answer", "")
        matched_sizes = SIZE_PATTERN.findall(assistant_answer)

        if matched_sizes:
            return matched_sizes[0].upper()

    return None


def extract_preference(user_query, chat_history):
    current_preference = extract_size_preference(user_query)

    if current_preference:
        return current_preference

    if not chat_history:
        return None

    for chat_turn in reversed(chat_history):
        history_query = chat_turn.get("user_query", "")
        history_preference = extract_size_preference(history_query)

        if history_preference:
            return history_preference

    return None


def extract_current_product(user_query, chat_history):
    for product in PRODUCT_KEYWORDS:
        if product in user_query:
            return product

    if not chat_history:
        return None

    for chat_turn in reversed(chat_history):
        history_query = chat_turn.get("user_query", "")

        for product in PRODUCT_KEYWORDS:
            if product in history_query:
                return product

    return None


def build_ignored_history_reason(user_query, used_history):
    if has_complete_measurements(user_query):
        return "当前问题已提供新的身高体重，忽略历史身高体重。"

    if used_history["has_reference_words"] or used_history["measurements_query"]:
        return "仅使用与当前追问相关的最近历史信息，忽略其他历史。"

    return "当前问题不依赖历史，未使用聊天历史。"


def build_memory_query(user_query, used_history):
    lines = ["历史有效信息："]

    if used_history["measurements_query"]:
        lines.append(f"用户历史身高体重：{used_history['measurements_query']}")

    if used_history["last_recommended_size"]:
        lines.append(f"上一轮推荐尺码：{used_history['last_recommended_size']}")

    if used_history["preference"]:
        lines.append(f"用户偏好：{used_history['preference']}")

    if used_history["current_product"]:
        lines.append(f"当前商品：{used_history['current_product']}")

    lines.append(f"当前问题：{user_query}")
    return "\n".join(lines)


def run_memory_tool(user_query, chat_history=None, intent_result=None):
    chat_history = chat_history or []
    current_has_measurements = has_complete_measurements(user_query)

    used_history = {
        "latest_user_query": chat_history[-1]["user_query"] if chat_history else None,
        "measurements_query": None if current_has_measurements else extract_measurements_query(chat_history),
        "last_recommended_size": None if current_has_measurements else extract_last_recommended_size(chat_history),
        "preference": extract_preference(user_query, chat_history),
        "current_product": extract_current_product(user_query, chat_history),
        "has_reference_words": has_reference_words(user_query),
    }
    need_history = bool(
        used_history["measurements_query"]
        or used_history["last_recommended_size"]
    )

    return {
        "used_history": used_history,
        "ignored_history_reason": build_ignored_history_reason(user_query, used_history),
        "need_history": need_history,
        "memory_query": build_memory_query(user_query, used_history),
        "intent_result": intent_result,
    }


def main():
    test_history = [
        {
            "user_query": "我身高168，体重65kg，想买一件日常穿的T恤",
            "assistant_answer": "建议选择 L 码。",
        }
    ]
    test_cases = [
        ("那我想宽松一点呢？", test_history),
        ("我身高188，体重75kg，想买T恤", test_history),
        ("那 L 会不会太紧？", test_history),
    ]

    for query, history in test_cases:
        print(query)
        print(run_memory_tool(query, history))
        print("-" * 60)


if __name__ == "__main__":
    main()
