from clothing_assistant.infrastructure.vector_store import load_vector_store_meta, search_similar_chunks


DEFAULT_AGENT_RAG_TOP_K = 3


def build_rag_retrieval_query(user_query, query_type=None):
    """把用户问题补充成更适合知识库检索的查询文本。"""
    base_query = user_query.strip()

    if query_type == "recommendation":
        return (
            f"{base_query}。"
            "导购推荐，适合场景，颜色选择，材质，季节，通勤，日常穿搭。"
        )

    if query_type == "inventory":
        return (
            f"{base_query}。"
            "颜色选择，商品颜色，库存颜色，可选颜色，黑色，白色，灰色，蓝色。"
        )

    if query_type == "policy":
        return (
            f"{base_query}。"
            "退换货政策，发货时间，物流说明，售后规则，退款，换货，运费。"
        )

    return (
        f"{base_query}。"
        "商品知识，颜色，材质，洗涤，养护，场景，季节，适合人群。"
    )


def simplify_chunk(chunk):
    """整理检索结果，保留 Agent debug 和后续回答生成需要的字段。"""
    return {
        "chunk_id": chunk["chunk_id"],
        "file_name": chunk["file_name"],
        "content": chunk["content"],
        "score": chunk["score"],
    }


def safe_load_vector_store_meta():
    try:
        return load_vector_store_meta()
    except Exception:
        return {}


def run_rag_tool(user_query, top_k=DEFAULT_AGENT_RAG_TOP_K, metadata_filter=None, query_type=None):
    """Agent RAG 工具入口：只负责检索知识库，不负责生成最终回答。"""
    retrieval_query = build_rag_retrieval_query(user_query, query_type=query_type)
    try:
        retrieved_chunks = search_similar_chunks(
            retrieval_query,
            top_k=top_k,
            metadata_filter=metadata_filter,
        )
    except FileNotFoundError:
        retrieved_chunks = []

    simplified_chunks = [simplify_chunk(chunk) for chunk in retrieved_chunks]

    return {
        "retrieval_query": retrieval_query,
        "retrieved_chunks": simplified_chunks,
        "source_count": len(simplified_chunks),
        "rag_meta": safe_load_vector_store_meta(),
    }


def main():
    test_queries = [
        ("这件衣服适合夏天吗？", "product"),
        ("日常通勤适合什么颜色？", "product"),
        ("我想买一件适合通勤的外套", "recommendation"),
    ]

    for query, query_type in test_queries:
        print(query)
        result = run_rag_tool(query, query_type=query_type)
        print(f"retrieval_query: {result['retrieval_query']}")
        print(f"source_count: {result['source_count']}")

        for index, chunk in enumerate(result["retrieved_chunks"], start=1):
            print(f"{index}. {chunk['file_name']} | {chunk['chunk_id']} | score={chunk['score']:.4f}")
            print(chunk["content"])

        print("-" * 60)


if __name__ == "__main__":
    main()
