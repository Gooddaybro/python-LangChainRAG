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

RECOMMENDATION_KEYWORDS = [
    "推荐",
    "想买",
    "适合通勤",
    "适合日常",
    "导购",
    "挑一件",
    "选一件",
    "买一件",
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


def normalize_query(user_query):
    return user_query.strip().lower()


def contains_any(text, keywords):
    return any(keyword in text for keyword in keywords)


def has_measurement_signal(text):
    """判断用户问题里是否出现身高、体重这类尺码强信号。"""
    height_pattern = r"(身高\s*)?\d{2,3}\s*(cm|厘米)"
    weight_pattern = r"(体重\s*)?\d{2,3}\s*(kg|公斤|斤)"
    return bool(re.search(height_pattern, text)) or bool(re.search(weight_pattern, text))


def needs_history(user_query):
    """判断当前问题是否依赖上一轮上下文。"""
    normalized_query = normalize_query(user_query)
    return contains_any(normalized_query, HISTORY_REFERENCE_KEYWORDS)


def build_router_result(intent, query_type, need_history, reason):
    """统一 Router 输出结构，避免后续节点到处猜字段名。"""
    return {
        "intent": intent,
        "need_history": need_history,
        "reason": reason,
        "query_type": query_type,
    }


def intent_router(user_query):
    """规则版意图识别器：先保证稳定可解释，后续再考虑升级成模型 Router。"""
    normalized_query = normalize_query(user_query)
    need_history = needs_history(user_query)

    # 路由顺序本身就是业务规则：闲聊和政策先短路，尺码优先识别强信号。
    # Learning: 以后如果换成 LLM Router，这些顺序要转成 prompt 或结构化评测。
    if not normalized_query:
        return build_router_result(
            INTENT_UNKNOWN,
            "unknown",
            False,
            "用户问题为空，无法判断意图。",
        )

    if contains_any(normalized_query, CHAT_KEYWORDS):
        return build_router_result(
            INTENT_CHAT,
            "chat",
            need_history,
            "命中普通闲聊关键词。",
        )

    if contains_any(normalized_query, POLICY_KEYWORDS):
        return build_router_result(
            INTENT_POLICY_QA,
            "policy",
            need_history,
            "命中退换、物流、发货或售后相关关键词。",
        )

    if contains_any(normalized_query, INVENTORY_KEYWORDS):
        return build_router_result(
            INTENT_INVENTORY_CHECK,
            "inventory",
            need_history,
            "命中库存、颜色是否有货相关关键词。",
        )

    if has_measurement_signal(normalized_query) or contains_any(normalized_query, SIZE_KEYWORDS):
        size_need_history = need_history or not has_measurement_signal(normalized_query)
        reason = "命中身高体重或尺码偏好相关信息。"

        if size_need_history and not has_measurement_signal(normalized_query):
            reason = "命中尺码偏好，但当前问题缺少身高体重，需要尝试从历史补充。"

        return build_router_result(
            INTENT_SIZE_RECOMMENDATION,
            "size",
            size_need_history,
            reason,
        )

    if contains_any(normalized_query, RECOMMENDATION_KEYWORDS):
        return build_router_result(
            INTENT_RECOMMENDATION,
            "recommendation",
            need_history,
            "命中导购推荐相关关键词。",
        )

    if contains_any(normalized_query, PRODUCT_QA_KEYWORDS):
        return build_router_result(
            INTENT_PRODUCT_QA,
            "product",
            need_history,
            "命中商品知识、颜色、洗涤或季节适配相关关键词。",
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
