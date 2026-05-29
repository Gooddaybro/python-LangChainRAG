from clothing_assistant.tools.rag_tool import run_rag_tool


POLICY_KEYWORDS = [
    "退货",
    "换货",
    "退款",
    "退换",
    "售后",
    "物流",
    "发货",
    "快递",
    "运费",
    "政策",
    "签收",
]

NO_POLICY_SOURCE_ANSWER = (
    "当前知识库没有退换货、物流或售后政策资料，"
    "建议查看店铺政策页面或联系人工客服确认。"
)


def contains_any(text, keywords):
    return any(keyword in text for keyword in keywords)


def is_policy_chunk(chunk):
    """判断检索结果是否真的包含政策类资料。"""
    searchable_text = f"{chunk['file_name']}\n{chunk['content']}"
    return contains_any(searchable_text, POLICY_KEYWORDS)


def build_no_policy_source_result(user_query, rag_result):
    return {
        "has_policy_source": False,
        "policy_answer": NO_POLICY_SOURCE_ANSWER,
        "retrieval_query": rag_result["retrieval_query"],
        "policy_chunks": [],
        "raw_retrieved_chunks": rag_result["retrieved_chunks"],
        "source_count": 0,
        "reason": f"用户问题“{user_query}”属于政策类问题，但当前检索结果没有政策来源。",
    }


def run_policy_tool(user_query, top_k=5):
    """Agent 政策工具入口：有政策来源才回答，没有来源就明确兜底。"""
    rag_result = run_rag_tool(
        user_query,
        top_k=top_k,
        query_type="policy",
    )
    policy_chunks = [
        chunk
        for chunk in rag_result["retrieved_chunks"]
        if is_policy_chunk(chunk)
    ]

    if not policy_chunks:
        return build_no_policy_source_result(user_query, rag_result)

    return {
        "has_policy_source": True,
        "policy_answer": None,
        "retrieval_query": rag_result["retrieval_query"],
        "policy_chunks": policy_chunks,
        "raw_retrieved_chunks": rag_result["retrieved_chunks"],
        "source_count": len(policy_chunks),
        "reason": "检索结果中存在政策类资料，可交给后续 answer_generator 生成回答。",
    }


def main():
    test_queries = [
        "可以退货吗？",
        "什么时候发货？",
        "有售后吗？",
    ]

    for query in test_queries:
        print(query)
        result = run_policy_tool(query)
        print(f"has_policy_source: {result['has_policy_source']}")
        print(f"policy_answer: {result['policy_answer']}")
        print(f"retrieval_query: {result['retrieval_query']}")
        print(f"source_count: {result['source_count']}")
        print("raw_retrieved_chunks:")

        for index, chunk in enumerate(result["raw_retrieved_chunks"], start=1):
            print(f"{index}. {chunk['file_name']} | {chunk['chunk_id']} | score={chunk['score']:.4f}")

        print("-" * 60)


if __name__ == "__main__":
    main()
