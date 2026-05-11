from clothing_rag_demo.agent.router import (
    INTENT_CHAT,
    INTENT_INVENTORY_CHECK,
    INTENT_POLICY_QA,
    INTENT_PRODUCT_QA,
    INTENT_RECOMMENDATION,
    INTENT_SIZE_RECOMMENDATION,
    INTENT_UNKNOWN,
)


SIZE_HISTORY = [
    {
        "user_query": "我身高168，体重65kg，想买一件日常穿的T恤",
        "assistant_answer": "建议选择 L 码。",
    }
]


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
    },
]
