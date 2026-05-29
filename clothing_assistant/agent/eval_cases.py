"""固定评测用例。

这些 case 是 Agent 的最低行为契约：路由要识别什么意图、该选哪些工具、
什么时候必须兜底、什么时候必须命中 RAG。
"""

from clothing_assistant.agent.router import (
    INTENT_CHAT,
    INTENT_INVENTORY_CHECK,
    INTENT_POLICY_QA,
    INTENT_PRICE_CHECK,
    INTENT_PRODUCT_QA,
    INTENT_RECOMMENDATION,
    INTENT_SIZE_RECOMMENDATION,
    INTENT_UNKNOWN,
)


# 追问类尺码问题需要历史上下文，所以这里准备一段稳定的历史输入。
SIZE_HISTORY = [
    {
        "user_query": "我身高168，体重65kg，想买一件日常穿的T恤",
        "assistant_answer": "建议选择 L 码。",
    }
]


DEFAULT_CASE_EXECUTORS = ["pipeline", "langgraph"]


def get_case_executors(case):
    return case.get("executors", DEFAULT_CASE_EXECUTORS)


def case_supports_executor(case, executor_name):
    return executor_name in get_case_executors(case)


def get_expected_value(case, executor_name, key):
    """按 executor 读取期望值。

    Learning: 旧 pipeline 和 LangGraph 主线现在是对照关系，不再强制完全一致。
    生产图可以要求库存查结构化数据，而 pipeline 继续保留旧行为作为迁移参照。
    """
    executor_expected = case.get("expected_by_executor", {}).get(executor_name, {})
    return executor_expected.get(key, case[key])


# Learning: 这里不是测试“回答写得好不好”，而是测试 Agent 调度是否走对路。
# 语义质量评测以后可以单独加，不要和路由/工具选择评测混在一起。
EVAL_CASES = [
    {
        "name": "chat_identity",
        "query": "你是谁？",
        "expected_intent": INTENT_CHAT,
        "expected_tools": [],
        "expected_stop_reason": "direct_answer",
        "requires_rag": False,
    },
    {
        "name": "chat_hello",
        "query": "你好",
        "expected_intent": INTENT_CHAT,
        "expected_tools": [],
        "expected_stop_reason": "direct_answer",
        "requires_rag": False,
    },
    {
        "name": "unknown_out_of_scope",
        "query": "帮我写一首诗",
        "expected_intent": INTENT_UNKNOWN,
        "expected_tools": [],
        "expected_stop_reason": "direct_answer",
        "requires_rag": False,
    },
    {
        "name": "policy_return",
        "query": "可以退货吗？",
        "expected_intent": INTENT_POLICY_QA,
        "expected_tools": ["policy_tool"],
        "expected_stop_reason": "policy_fallback",
        "requires_rag": False,
    },
    {
        "name": "policy_shipping",
        "query": "什么时候发货？",
        "expected_intent": INTENT_POLICY_QA,
        "expected_tools": ["policy_tool"],
        "expected_stop_reason": "policy_fallback",
        "requires_rag": False,
    },
    {
        "name": "size_measurements",
        "query": "我 175cm 70kg 穿什么码？",
        "expected_intent": INTENT_SIZE_RECOMMENDATION,
        "expected_tools": ["size_tool"],
        "expected_stop_reason": "final_answer",
        "requires_rag": False,
    },
    {
        "name": "size_follow_up_with_history",
        "query": "那我想宽松一点呢？",
        "chat_history": SIZE_HISTORY,
        "expected_intent": INTENT_SIZE_RECOMMENDATION,
        "expected_tools": ["size_tool"],
        "expected_stop_reason": "final_answer",
        "requires_rag": False,
    },
    {
        "name": "product_qa_summer",
        "query": "这件衣服适合夏天吗？",
        "expected_intent": INTENT_PRODUCT_QA,
        "expected_tools": ["rag_tool"],
        "expected_stop_reason": "final_answer",
        "requires_rag": True,
    },
    {
        "name": "product_color",
        "query": "日常通勤推荐什么颜色？",
        "expected_intent": INTENT_RECOMMENDATION,
        "expected_tools": ["rag_tool"],
        "expected_stop_reason": "final_answer",
        "requires_rag": True,
    },
    {
        "name": "inventory_color",
        "query": "黑色有货吗？",
        "expected_intent": INTENT_INVENTORY_CHECK,
        "expected_tools": ["rag_tool"],
        "expected_stop_reason": "final_answer",
        "requires_rag": True,
        "expected_by_executor": {
            "langgraph": {
                "expected_tools": [],
                "expected_stop_reason": "missing_info",
                "requires_rag": False,
            }
        },
    },
    {
        "name": "recommendation_commute",
        "query": "我想买一件适合通勤的外套",
        "expected_intent": INTENT_RECOMMENDATION,
        "expected_tools": ["rag_tool"],
        "expected_stop_reason": "final_answer",
        "requires_rag": True,
    },
    {
        "name": "product_size_combined",
        "query": "我身高175cm，体重70kg，这件T恤适合我吗？",
        "expected_intent": INTENT_SIZE_RECOMMENDATION,
        "expected_tools": ["rag_tool", "size_tool"],
        "expected_stop_reason": "final_answer",
        "requires_rag": True,
        "expected_by_executor": {
            "langgraph": {
                "expected_tools": ["size_tool", "rag_tool"],
            }
        },
    },
    {
        "name": "inventory_exact_black_l_langgraph",
        "query": "基础款纯棉T恤黑色L码有货吗？",
        "executors": ["langgraph"],
        "expected_intent": INTENT_INVENTORY_CHECK,
        "expected_tools": ["structured_lookup"],
        "expected_stop_reason": "final_answer",
        "requires_rag": False,
    },
    {
        "name": "inventory_missing_product_langgraph",
        "query": "黑色M码有货吗？",
        "executors": ["langgraph"],
        "expected_intent": INTENT_INVENTORY_CHECK,
        "expected_tools": [],
        "expected_stop_reason": "missing_info",
        "requires_rag": False,
    },
    {
        "name": "inventory_missing_color_langgraph",
        "query": "基础款纯棉T恤L码有货吗？",
        "executors": ["langgraph"],
        "expected_intent": INTENT_INVENTORY_CHECK,
        "expected_tools": [],
        "expected_stop_reason": "missing_info",
        "requires_rag": False,
    },
    {
        "name": "inventory_unknown_color_langgraph",
        "query": "基础款纯棉T恤红色M码有货吗？",
        "executors": ["langgraph"],
        "expected_intent": INTENT_INVENTORY_CHECK,
        "expected_tools": ["structured_lookup"],
        "expected_stop_reason": "final_answer",
        "requires_rag": False,
    },
    {
        "name": "price_exact_langgraph",
        "query": "基础款纯棉T恤多少钱？",
        "executors": ["langgraph"],
        "expected_intent": INTENT_PRICE_CHECK,
        "expected_tools": ["structured_lookup"],
        "expected_stop_reason": "final_answer",
        "requires_rag": False,
    },
    {
        "name": "price_missing_product_langgraph",
        "query": "这件多少钱？",
        "executors": ["langgraph"],
        "expected_intent": INTENT_PRICE_CHECK,
        "expected_tools": [],
        "expected_stop_reason": "missing_info",
        "requires_rag": False,
    },
    {
        "name": "product_care_semantic_langgraph",
        "query": "纯棉T恤怎么洗？",
        "executors": ["langgraph"],
        "expected_intent": INTENT_PRODUCT_QA,
        "expected_tools": ["rag_tool"],
        "expected_stop_reason": "final_answer",
        "requires_rag": True,
    },
    {
        "name": "history_inventory_follow_up_still_requires_product_langgraph",
        "query": "那黑色M码有货吗？",
        "chat_history": SIZE_HISTORY,
        "executors": ["langgraph"],
        "expected_intent": INTENT_INVENTORY_CHECK,
        "expected_tools": [],
        "expected_stop_reason": "missing_info",
        "requires_rag": False,
    },
    {
        "name": "size_missing_measurements_langgraph",
        "query": "我穿什么码？",
        "executors": ["langgraph"],
        "expected_intent": INTENT_SIZE_RECOMMENDATION,
        "expected_tools": [],
        "expected_stop_reason": "missing_info",
        "requires_rag": False,
    },
    {
        "name": "price_outerwear_exact_langgraph",
        "query": "通勤轻薄外套价格是多少？",
        "executors": ["langgraph"],
        "expected_intent": INTENT_PRICE_CHECK,
        "expected_tools": ["structured_lookup"],
        "expected_stop_reason": "final_answer",
        "requires_rag": False,
    },
]
