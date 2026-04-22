from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

from config_data import (
    DEFAULT_TEST_QUERY,
    DEFAULT_TOP_K,
    EMBEDDING_MODEL_NAME,
    VECTOR_COLLECTION_NAME,
    VECTOR_DB_DIR,
)
from knowledge_base import build_knowledge_chunks, load_knowledge_files


# 初始化 embedding 模型：后面知识文本和用户问题都会走同一个向量模型。
def get_embeddings():
    return DashScopeEmbeddings(model=EMBEDDING_MODEL_NAME)


# 把我们自己的 chunk 结构转成 LangChain / Chroma 能接收的 Document 对象。
def build_documents_from_chunks(knowledge_chunks):
    documents = []

    for chunk in knowledge_chunks:
        documents.append(
            Document(
                page_content=chunk["content"],
                metadata={
                    "chunk_id": chunk["chunk_id"],
                    "file_name": chunk["file_name"],
                    "file_path": chunk["file_path"],
                },
            )
        )

    return documents


# 重建向量库：当前最小版本每次都以当前知识文件为准，先清空旧集合，再全量写入。
def rebuild_vector_store(knowledge_chunks):
    VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
    embeddings = get_embeddings()
    documents = build_documents_from_chunks(knowledge_chunks)

    # 先连接到同名集合；如果集合存在，则删掉旧集合，避免重复入库。
    existing_store = Chroma(
        collection_name=VECTOR_COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(VECTOR_DB_DIR),
    )
    existing_store.delete_collection()

    vector_store = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=str(VECTOR_DB_DIR),
        collection_name=VECTOR_COLLECTION_NAME,
    )

    return vector_store


# 根据用户问题检索最相关的知识块，并把结果整理成更容易打印和后续使用的结构。
def search_similar_chunks(query, top_k=DEFAULT_TOP_K, metadata_filter=None):
    embeddings = get_embeddings()
    vector_store = Chroma(
        collection_name=VECTOR_COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(VECTOR_DB_DIR),
    )

    results = vector_store.similarity_search_with_score(
        query,
        k=top_k,
        filter=metadata_filter,
    )
    matched_chunks = []

    for document, score in results:
        matched_chunks.append(
            {
                "chunk_id": document.metadata.get("chunk_id"),
                "file_name": document.metadata.get("file_name"),
                "file_path": document.metadata.get("file_path"),
                "content": document.page_content,
                "score": score,
            }
        )

    return matched_chunks


# 从本地知识文件直接完成“读取 -> 切块 -> 重建向量库”，方便上传页在文件变化时直接调用。
def rebuild_vector_store_from_local_knowledge():
    knowledge_docs = load_knowledge_files()
    knowledge_chunks = build_knowledge_chunks(knowledge_docs)
    vector_store = rebuild_vector_store(knowledge_chunks)

    return vector_store, knowledge_docs, knowledge_chunks


def main():
    _, knowledge_docs, knowledge_chunks = rebuild_vector_store_from_local_knowledge()
    matched_chunks = search_similar_chunks(DEFAULT_TEST_QUERY)

    print(f"已完成向量入库，共写入 {len(knowledge_chunks)} 个文本块。")
    print(f"测试问题：{DEFAULT_TEST_QUERY}")
    print("检索结果：")

    for index, chunk in enumerate(matched_chunks, start=1):
        print(
            f"[{index}] 文件: {chunk['file_name']} | chunk: {chunk['chunk_id']} | "
            f"score: {chunk['score']:.4f}"
        )
        print(chunk["content"])
        print("-" * 60)


if __name__ == "__main__":
    main()
