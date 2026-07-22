"""规则版意图路由器。

这个模块像 pipeline 的“分拣员”：先判断用户问题属于哪类意图，
后面的 ToolRegistry 再根据这个意图决定该不该调用具体工具。
"""

import re

# MVP 阶段先用固定意图字符串，保证测试和评测报告可以稳定断言。
INTENT_SIZE_RECOMMENDATION = "size_recommendation"
INTENT_PRODUCT_QA = "product_qa"
INTENT_POLICY_QA = "policy_qa"
INTENT_RECOMMENDATION = "recommendation"
INTENT_INVENTORY_CHECK = "inventory_check"
INTENT_PRICE_CHECK = "price_check"
INTENT_CHAT = "chat"
INTENT_UNKNOWN = "unknown"


HISTORY_REFERENCE_KEYWORDS = [
    "那",
    "这个",
    "这件",
    "刚才",
    "上次",
    "前面",
    "它",
    "我呢",
    "那个",
    "还适合",
    "会不会",
]

SIZE_KEYWORDS = [
    "尺码",
    "码数",
    "穿什么码",
    "穿多大",
    "多大码",
    "推荐码",
    "合身",
    "宽松",
    "偏紧",
    "太紧",
    "太大",
    "太小",
    "s码",
    "m码",
    "l码",
    "xl",
]

POLICY_KEYWORDS = [
    "退货",
    "换货",
    "退款",
    "退换",
    "售后",
    "发货",
    "物流",
    "快递",
    "运费",
    "几天到",
    "什么时候发",
    "多久发",
]

INVENTORY_KEYWORDS = [
    "有货",
    "库存",
    "还有吗",
    "缺货",
    "补货",
    "现货",
    "黑色有",
    "白色有",
    "颜色有",
]

PRICE_KEYWORDS = [
    "多少钱",
    "价格",
    "售价",
    "几块",
    "几元",
    "贵吗",
]

RECOMMENDATION_KEYWORDS = [
    "推荐",
    "穿搭",
    "想买",
    "适合通勤",
    "适合日常",
    "导购",
    "挑一件",
    "选一件",
    "怎么选",
    "买一件",
    "学生党",
    "大学生",
    "上课",
    "校园",
    "显高",
    "显腿长",
    "小个子",
    "遮肉",
    "不显胖",
    "平价",
    "便宜",
    "不贵",
    "预算有限",
    "百搭",
    "好搭",
    "一衣多穿",
    "约会穿搭",
    "上班通勤",
    "秋冬保暖",
    "裙子",
    "半裙",
    "半身裙",
    "百褶裙",
    "A字裙",
    "a字裙",
    "连衣裙",
    "男生",
    "男性",
    "男士",
    "男款",
    "女生",
    "女性",
    "女士",
    "女款",
]

PRODUCT_QA_KEYWORDS = [
    "面料",
    "材质",
    "洗",
    "洗涤",
    "养护",
    "颜色",
    "显瘦",
    "适合夏天",
    "适合冬天",
    "透气",
    "会不会热",
    "会不会透",
]

CHAT_KEYWORDS = [
    "你好",
    "您好",
    "谢谢",
    "你是谁",
    "你能做什么",
]

PRODUCT_REFERENCE_KEYWORDS = ["这件", "这款", "这个商品", "这件衣服"]
PRODUCT_FIT_QUESTION_KEYWORDS = ["合适吗", "适合吗", "适不适合"]

OUTFIT_ADVICE_KEYWORDS = [
    "怎么穿",
    "如何穿",
    "穿什么好",
    "怎么搭",
    "如何搭配",
    "搭配什么",
    "穿搭",
    "该怎么选",
]

EXPLICIT_SIZE_KEYWORDS = [
    "尺码",
    "码数",
    "穿什么码",
    "穿多大",
    "多大码",
    "推荐码",
]

REQUEST_TYPE_ROUTES = {
    "CHAT": (INTENT_CHAT, "chat"),
    "OUTFIT_ADVICE": (INTENT_RECOMMENDATION, "recommendation"),
    "PRODUCT_RECOMMENDATION": (INTENT_RECOMMENDATION, "recommendation"),
    "SIZE_RECOMMENDATION": (INTENT_SIZE_RECOMMENDATION, "size"),
    "PRODUCT_QA": (INTENT_PRODUCT_QA, "product"),
    "POLICY_QA": (INTENT_POLICY_QA, "policy"),
    "INVENTORY_CHECK": (INTENT_INVENTORY_CHECK, "inventory"),
    "PRICE_CHECK": (INTENT_PRICE_CHECK, "price"),
    "UNKNOWN": (INTENT_UNKNOWN, "unknown"),
}

DEFAULT_CAPABILITIES = {
    "OUTFIT_ADVICE": ["OUTFIT_PLAN", "PRODUCT_SELECTION"],
    "PRODUCT_RECOMMENDATION": ["PRODUCT_SELECTION"],
    "SIZE_RECOMMENDATION": ["SIZE_GUIDANCE"],
}


def normalize_query(user_query):
    return user_query.strip().lower()


def contains_any(text, keywords):
    return any(keyword in text for keyword in keywords)


def has_measurement_signal(text):
    """判断用户问题里是否出现身高、体重这类尺码强信号。"""
    height_pattern = r"(身高\s*)?\d{2,3}\s*(cm|厘米)"
    weight_pattern = r"(体重\s*)?\d{2,3}\s*(kg|公斤|斤)"
    return bool(re.search(height_pattern, text)) or bool(re.search(weight_pattern, text)) or has_bare_measurement_pair(text)


def has_bare_measurement_pair(text):
    """识别“177 130”这类身高 + 体重斤的真实用户省略写法。"""
    numbers = [float(value) for value in re.findall(r"(?<!\d)(\d{2,3})(?!\d)", text)]

    for first, second in zip(numbers, numbers[1:]):
        if 140 <= first <= 210 and 70 <= second <= 260:
            return True

    return False


def needs_history(user_query):
    """判断当前问题是否依赖上一轮上下文。"""
    normalized_query = normalize_query(user_query)
    return contains_any(normalized_query, HISTORY_REFERENCE_KEYWORDS)


def build_router_result(
    intent,
    query_type,
    need_history,
    reason,
    request_type=None,
    requested_capabilities=None,
):
    """统一 Router 输出结构，避免后续节点到处猜字段名。"""
    return {
        "intent": intent,
        "need_history": need_history,
        "reason": reason,
        "query_type": query_type,
        "request_type": request_type or query_type.upper(),
        "requested_capabilities": list(requested_capabilities or []),
    }


def normalize_capabilities(values):
    """Normalize capability values while preserving Java's declared order."""
    result = []
    for value in values or []:
        normalized = str(value or "").strip().upper()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def route_java_intent(demand_intent, need_history):
    """Use the current Java main task as the normative routing authority."""
    if not isinstance(demand_intent, dict):
        return None
    version = normalize_query(str(demand_intent.get("version") or ""))
    if version not in {"demand-intent-v2", "demand-intent-v3"}:
        return None

    request_type = str(
        demand_intent.get("requestType") or demand_intent.get("request_type") or ""
    ).strip().upper()
    route = REQUEST_TYPE_ROUTES.get(request_type)
    if not route:
        return None

    capabilities = normalize_capabilities(
        demand_intent.get("requestedCapabilities")
        or demand_intent.get("requested_capabilities")
        or DEFAULT_CAPABILITIES.get(request_type, [])
    )
    return build_router_result(
        route[0],
        route[1],
        need_history,
        f"采用 Java {version} 提供的规范主任务与附加能力。",
        request_type,
        capabilities,
    )


def is_greeting_only(text):
    """Return true only when removing greeting phrases leaves no real request."""
    remaining = text
    for keyword in CHAT_KEYWORDS:
        remaining = remaining.replace(keyword, "")
    remaining = re.sub(r"[\s，。！？、,.!?~～]+", "", remaining)
    return not remaining


def has_recommendation_demand(demand_intent):
    """Return whether Java already supplied at least one validated shopping slot."""
    if not isinstance(demand_intent, dict):
        return False

    if any(
        demand_intent.get(key)
        for key in (
            "targetGender",
            "target_gender",
            "category",
            "budgetMax",
            "budget_max",
            "scene",
            "style",
            "attributes",
        )
    ):
        return True

    return any(
        isinstance(constraint, dict) and bool(constraint.get("values"))
        for collection in ("hardFilters", "softPreferences")
        for constraint in demand_intent.get(collection) or []
    )


def intent_router(user_query, demand_intent=None):
    """规则版意图识别器：先保证稳定可解释，后续再考虑升级成模型 Router。"""
    normalized_query = normalize_query(user_query)
    need_history = needs_history(user_query)

    java_intent_result = route_java_intent(demand_intent, need_history)
    if java_intent_result is not None:
        return java_intent_result

    # 路由顺序本身就是业务规则：闲聊和政策先短路，尺码优先识别强信号。
    # Learning: 以后如果换成 LLM Router，这些顺序要转成 prompt 或结构化评测。
    if not normalized_query:
        return build_router_result(
            INTENT_UNKNOWN,
            "unknown",
            False,
            "用户问题为空，无法判断意图。",
        )

    if contains_any(normalized_query, POLICY_KEYWORDS):
        return build_router_result(
            INTENT_POLICY_QA,
            "policy",
            need_history,
            "命中退换、物流、发货或售后相关关键词。",
            "POLICY_QA",
        )

    if contains_any(normalized_query, INVENTORY_KEYWORDS):
        return build_router_result(
            INTENT_INVENTORY_CHECK,
            "inventory",
            need_history,
            "命中库存、颜色是否有货相关关键词。",
            "INVENTORY_CHECK",
        )

    if contains_any(normalized_query, PRICE_KEYWORDS):
        return build_router_result(
            INTENT_PRICE_CHECK,
            "price",
            need_history,
            "命中价格或售价相关关键词。",
            "PRICE_CHECK",
        )

    has_measurements = has_measurement_signal(normalized_query)
    asks_for_size = contains_any(normalized_query, SIZE_KEYWORDS) or (
        has_measurements and contains_any(normalized_query, ["适合我", "合适吗", "合不合适"])
    )
    asks_for_outfit = contains_any(normalized_query, OUTFIT_ADVICE_KEYWORDS)

    if asks_for_outfit:
        capabilities = ["OUTFIT_PLAN", "PRODUCT_SELECTION"]
        if asks_for_size:
            capabilities.append("SIZE_GUIDANCE")
        reason = "命中穿搭建议问题。"
        if has_measurements:
            reason = "命中穿搭建议问题；身高体重作为辅助信息。"
        return build_router_result(
            INTENT_RECOMMENDATION,
            "recommendation",
            need_history,
            reason,
            "OUTFIT_ADVICE",
            capabilities,
        )

    if asks_for_size:
        size_need_history = need_history or not has_measurement_signal(normalized_query)
        reason = "用户明确询问尺码；身高体重用于尺码计算。"

        if size_need_history and not has_measurement_signal(normalized_query):
            reason = "命中尺码偏好，但当前问题缺少身高体重，需要尝试从历史补充。"

        return build_router_result(
            INTENT_SIZE_RECOMMENDATION,
            "size",
            size_need_history,
            reason,
            "SIZE_RECOMMENDATION",
            ["SIZE_GUIDANCE"],
        )

    if has_recommendation_demand(demand_intent):
        return build_router_result(
            INTENT_RECOMMENDATION,
            "recommendation",
            need_history,
            "Java 已提供经过校验的结构化导购需求。",
            "PRODUCT_RECOMMENDATION",
            ["PRODUCT_SELECTION"],
        )

    if contains_any(normalized_query, RECOMMENDATION_KEYWORDS):
        return build_router_result(
            INTENT_RECOMMENDATION,
            "recommendation",
            need_history,
            "命中导购推荐相关关键词。",
            "PRODUCT_RECOMMENDATION",
            ["PRODUCT_SELECTION"],
        )

    if contains_any(normalized_query, PRODUCT_QA_KEYWORDS):
        return build_router_result(
            INTENT_PRODUCT_QA,
            "product",
            need_history,
            "命中商品知识、颜色、洗涤或季节适配相关关键词。",
            "PRODUCT_QA",
        )

    if contains_any(normalized_query, PRODUCT_REFERENCE_KEYWORDS) and contains_any(
        normalized_query, PRODUCT_FIT_QUESTION_KEYWORDS
    ):
        return build_router_result(
            INTENT_PRODUCT_QA,
            "product",
            need_history,
            "命中指定商品的适用性问题。",
            "PRODUCT_QA",
        )

    if is_greeting_only(normalized_query):
        return build_router_result(
            INTENT_CHAT,
            "chat",
            need_history,
            "去除问候词后没有其他有效请求。",
            "CHAT",
        )

    return build_router_result(
        INTENT_UNKNOWN,
        "unknown",
        need_history,
        "没有命中当前 MVP Router 支持的明确意图。",
    )


def main():
    test_queries = [
        "我 175cm 70kg 穿什么码？",
        "我喜欢宽松一点，应该选什么？",
        "那黑色有货吗？",
        "可以退货吗？",
        "这件衣服适合夏天吗？",
        "那 L 会不会太紧？",
        "什么时候发货？",
        "我想买一件适合通勤的外套",
        "刚才那个尺码还适合我吗？",
        "你是谁？",
    ]

    for query in test_queries:
        print(query)
        print(intent_router(query))
        print("-" * 60)


if __name__ == "__main__":
    main()
