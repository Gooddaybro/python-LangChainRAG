import json
import math
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from langchain_community.embeddings import DashScopeEmbeddings

from clothing_assistant.config_data import (
    DEFAULT_TEST_QUERY,
    DEFAULT_TOP_K,
    EMBEDDING_MODEL_NAME,
    VECTOR_DB_DIR,
)
from clothing_assistant.infrastructure.knowledge_base import build_knowledge_chunks, load_knowledge_files


_EMBEDDINGS_CACHE = None
_VECTOR_DATA_CACHE = None
VECTOR_STORE_FILE = VECTOR_DB_DIR / "simple_vector_store.json"
VECTOR_STORE_META_FILE = VECTOR_DB_DIR / "vector_store_meta.json"


# 初始化 embedding 模型：知识文本和用户问题必须使用同一个向量模型，向量才有可比性。
def get_embeddings():
    global _EMBEDDINGS_CACHE

    # Streamlit 点击按钮会重跑页面脚本；缓存模型对象可以避免重复初始化。
    if _EMBEDDINGS_CACHE is None:
        _EMBEDDINGS_CACHE = DashScopeEmbeddings(model=EMBEDDING_MODEL_NAME)

    return _EMBEDDINGS_CACHE


# 读取本地 JSON 向量库：这个最小版本不用 Chroma，避免 SQLite/Rust 后端在本机环境里反复报错。
def load_vector_data():
    global _VECTOR_DATA_CACHE

    if _VECTOR_DATA_CACHE is not None:
        return _VECTOR_DATA_CACHE

    if not VECTOR_STORE_FILE.exists():
        raise FileNotFoundError("向量库文件不存在，请先上传知识文件或运行 vector_stores.py 重建向量库。")

    with VECTOR_STORE_FILE.open("r", encoding="utf-8") as file:
        _VECTOR_DATA_CACHE = json.load(file)

    return _VECTOR_DATA_CACHE


def build_source_file_meta(knowledge_chunks):
    source_paths = {}

    for chunk in knowledge_chunks:
        file_name = chunk["file_name"]
        file_path = chunk.get("file_path")
        source_paths[file_name] = file_path

    source_files = []

    for file_name, file_path in sorted(source_paths.items()):
        path = Path(file_path) if file_path else None
        if path and path.exists():
            content = path.read_bytes()
            updated_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        else:
            content = "\n".join(
                chunk["content"]
                for chunk in knowledge_chunks
                if chunk["file_name"] == file_name
            ).encode("utf-8")
            updated_at = None

        source_files.append(
            {
                "file_name": file_name,
                "sha256": sha256(content).hexdigest(),
                "updated_at": updated_at,
            }
        )

    return source_files


def build_vector_store_meta(knowledge_chunks):
    built_at = datetime.now(timezone.utc).isoformat()
    return {
        "version": built_at,
        "source_files": build_source_file_meta(knowledge_chunks),
        "chunk_count": len(knowledge_chunks),
        "embedding_provider": "dashscope",
        "built_at": built_at,
    }


def load_vector_store_meta():
    if not VECTOR_STORE_META_FILE.exists():
        return {}

    with VECTOR_STORE_META_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def _build_vector_store_status(ready, reason, meta=None):
    meta = meta or {}
    return {
        "ready": ready,
        "reason": reason,
        "chunk_count": meta.get("chunk_count", 0),
        "version": meta.get("version"),
        "built_at": meta.get("built_at"),
    }


def _source_hashes(source_files):
    return {
        item.get("file_name"): item.get("sha256")
        for item in source_files
        if item.get("file_name") and item.get("sha256")
    }


def get_vector_store_status():
    """Return safe readiness metadata without exposing vectors or knowledge text."""
    if not VECTOR_STORE_FILE.exists():
        return _build_vector_store_status(False, "missing_vector_store")

    if not VECTOR_STORE_META_FILE.exists():
        return _build_vector_store_status(False, "missing_vector_store_meta")

    try:
        meta = load_vector_store_meta()
    except (OSError, ValueError):
        return _build_vector_store_status(False, "invalid_vector_store_meta")

    if not isinstance(meta, dict):
        return _build_vector_store_status(False, "invalid_vector_store_meta")

    try:
        with VECTOR_STORE_FILE.open("r", encoding="utf-8") as file:
            records = json.load(file)
    except (OSError, ValueError):
        return _build_vector_store_status(False, "invalid_vector_store", meta)

    if not isinstance(records, list):
        return _build_vector_store_status(False, "invalid_vector_store", meta)

    chunk_count = meta.get("chunk_count")
    if not isinstance(chunk_count, int) or len(records) != chunk_count:
        return _build_vector_store_status(False, "chunk_count_mismatch", meta)

    meta_sources = meta.get("source_files")
    if not isinstance(meta_sources, list):
        return _build_vector_store_status(False, "invalid_vector_store_meta", meta)

    try:
        current_chunks = build_knowledge_chunks(load_knowledge_files())
        current_sources = build_source_file_meta(current_chunks)
    except (OSError, ValueError):
        return _build_vector_store_status(False, "source_files_changed", meta)

    current_hashes = _source_hashes(current_sources)
    stored_hashes = _source_hashes(meta_sources)
    if len(current_chunks) != chunk_count or current_hashes != stored_hashes:
        return _build_vector_store_status(False, "source_files_changed", meta)

    return _build_vector_store_status(True, "ready", meta)


# 计算两个向量的余弦距离：距离越小，说明用户问题和知识块越相似。
def cosine_distance(query_vector, chunk_vector):
    dot_value = sum(left * right for left, right in zip(query_vector, chunk_vector))
    query_norm = math.sqrt(sum(value * value for value in query_vector))
    chunk_norm = math.sqrt(sum(value * value for value in chunk_vector))

    if query_norm == 0 or chunk_norm == 0:
        return 1.0

    cosine_similarity = dot_value / (query_norm * chunk_norm)
    return 1 - cosine_similarity


# 把我们自己的 chunk 结构转成本地向量库记录，每条记录包含原文、元数据和 embedding。
def build_vector_records_from_chunks(knowledge_chunks):
    embeddings = get_embeddings()
    chunk_texts = [chunk["content"] for chunk in knowledge_chunks]
    chunk_vectors = embeddings.embed_documents(chunk_texts)
    vector_records = []

    for chunk, chunk_vector in zip(knowledge_chunks, chunk_vectors):
        vector_records.append(
            {
                "chunk_id": chunk["chunk_id"],
                "file_name": chunk["file_name"],
                "file_path": chunk["file_path"],
                "content": chunk["content"],
                "embedding": chunk_vector,
            }
        )

    return vector_records


# 重建向量库：当前最小版本每次都以当前知识文件为准，全量生成 embedding 后写入本地 JSON 文件。
def rebuild_vector_store(knowledge_chunks):
    global _VECTOR_DATA_CACHE

    VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
    vector_records = build_vector_records_from_chunks(knowledge_chunks)

    # 写入 JSON 是为了教学阶段可观察：能明确看到“文本块已经被转成向量并保存起来”。
    with VECTOR_STORE_FILE.open("w", encoding="utf-8") as file:
        json.dump(vector_records, file, ensure_ascii=False)

    with VECTOR_STORE_META_FILE.open("w", encoding="utf-8") as file:
        json.dump(build_vector_store_meta(knowledge_chunks), file, ensure_ascii=False)

    _VECTOR_DATA_CACHE = vector_records

    return vector_records


# 根据用户问题检索最相关的知识块，并把结果整理成更容易打印和后续使用的结构。
def search_similar_chunks(query, top_k=DEFAULT_TOP_K, metadata_filter=None):
    vector_records = load_vector_data()
    query_vector = get_embeddings().embed_query(query)
    matched_chunks = []

    for record in vector_records:
        if metadata_filter:
            is_matched = all(record.get(key) == value for key, value in metadata_filter.items())
            if not is_matched:
                continue

        score = cosine_distance(query_vector, record["embedding"])
        matched_chunks.append(
            {
                "chunk_id": record["chunk_id"],
                "file_name": record["file_name"],
                "file_path": record["file_path"],
                "content": record["content"],
                "score": score,
            }
        )

    matched_chunks.sort(key=lambda chunk: chunk["score"])
    return matched_chunks[:top_k]


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
