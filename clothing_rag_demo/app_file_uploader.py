# 管理员上传 3 份服装知识文件，并把它们保存到 data/ 目录。

from collections import Counter
import hashlib
import json

import streamlit as st

from config_data import DATA_DIR, FILE_HASH_RECORD_PATH, KNOWLEDGE_FILES
from knowledge_base import (
    build_knowledge_chunks,
    build_preview_text,
    load_knowledge_files,
)


# 固定本项目允许上传的知识文件名，后面会用它做严格校验。
EXPECTED_FILE_NAMES = set(KNOWLEDGE_FILES)


# 校验上传文件：只允许上传固定的 3 个 txt 文件，避免后续知识库读取失败。
def validate_uploaded_files(uploaded_files):
    uploaded_names = [uploaded_file.name for uploaded_file in uploaded_files]
    name_counter = Counter(uploaded_names)

    duplicate_names = sorted(
        file_name for file_name, count in name_counter.items() if count > 1
    )
    uploaded_name_set = set(uploaded_names)
    missing_names = sorted(EXPECTED_FILE_NAMES - uploaded_name_set)
    unexpected_names = sorted(uploaded_name_set - EXPECTED_FILE_NAMES)

    error_messages = []

    if len(uploaded_files) != len(KNOWLEDGE_FILES):
        error_messages.append(
            f"必须上传 {len(KNOWLEDGE_FILES)} 个文件，当前上传了 {len(uploaded_files)} 个。"
        )

    if duplicate_names:
        error_messages.append(f"发现重复文件：{', '.join(duplicate_names)}")

    if missing_names:
        error_messages.append(f"缺少文件：{', '.join(missing_names)}")

    if unexpected_names:
        error_messages.append(f"存在未约定的文件：{', '.join(unexpected_names)}")

    return error_messages


# 读取历史 MD5 记录：如果第一次运行还没有记录文件，就返回空字典。
def load_hash_record(record_path=FILE_HASH_RECORD_PATH):
    if not record_path.exists():
        return {}

    return json.loads(record_path.read_text(encoding="utf-8"))


# 计算文件内容的 MD5：这里直接基于 bytes 计算，避免字符串编码差异影响比较结果。
def calculate_file_md5(file_bytes):
    return hashlib.md5(file_bytes).hexdigest()


# 把上传文件整理成统一结构，后面校验、比较、保存都复用这份数据。
def build_uploaded_file_snapshots(uploaded_files):
    file_snapshots = []

    for uploaded_file in uploaded_files:
        file_bytes = uploaded_file.getvalue()
        file_snapshots.append(
            {
                "name": uploaded_file.name,
                "type": uploaded_file.type or "text/plain",
                "size": uploaded_file.size,
                "bytes": file_bytes,
                "md5": calculate_file_md5(file_bytes),
            }
        )

    return file_snapshots


# 比较上传文件和历史 MD5：只让真正变化的文件继续进入保存和后续处理。
def compare_uploaded_files(file_snapshots, hash_record):
    changed_files = []
    unchanged_files = []
    updated_hash_record = hash_record.copy()

    for snapshot in file_snapshots:
        file_name = snapshot["name"]
        old_md5 = hash_record.get(file_name)
        new_md5 = snapshot["md5"]

        if old_md5 == new_md5:
            unchanged_files.append(file_name)
        else:
            changed_files.append(file_name)
            updated_hash_record[file_name] = new_md5

    return changed_files, unchanged_files, updated_hash_record


# 保存上传文件：通过校验且确认内容变化后，再覆盖写入 data/。
def save_uploaded_files(file_snapshots, target_dir=DATA_DIR):
    target_dir.mkdir(parents=True, exist_ok=True)

    for snapshot in file_snapshots:
        target_path = target_dir / snapshot["name"]
        target_path.write_bytes(snapshot["bytes"])


# 保存最新 MD5 记录：后续再次上传同样内容时，就可以直接跳过无变化文件。
def save_hash_record(hash_record, record_path=FILE_HASH_RECORD_PATH):
    record_path.write_text(
        json.dumps(hash_record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# 把前几个 chunk 格式化成易读文本，方便在页面快速确认切块结果是否合理。
def build_chunk_preview_text(knowledge_chunks, limit=5):
    preview_lines = []

    for chunk in knowledge_chunks[:limit]:
        preview_lines.append(f"{chunk['chunk_id']} -> {chunk['content']}")

    return "\n".join(preview_lines)


st.title("知识库更新服务")
st.write("管理员只能上传以下 3 个知识文件，用来更新服装知识库：")
st.code("\n".join(KNOWLEDGE_FILES), language="text")

# 修正 1：允许一次上传多个 txt 文件；修正 2：上传说明要和固定业务文件名保持一致。
uploaded_files = st.file_uploader(
    "请上传 3 个 TXT 知识文件",
    type=["txt"],
    accept_multiple_files=True,
)

# 先展示当前已选文件，方便管理员在点击按钮前确认内容是否正确。
if uploaded_files:
    st.subheader("当前已选择的文件")

    for uploaded_file in uploaded_files:
        file_size_kb = uploaded_file.size / 1024
        st.write(
            f"文件名：{uploaded_file.name} | 类型：{uploaded_file.type or 'text/plain'} | 大小：{file_size_kb:.2f} KB"
        )


# 点击按钮后再执行保存和验证，避免用户一选中文件就立刻覆盖本地知识库。
if st.button("开始更新知识库"):
    if not uploaded_files:
        st.error("请先上传 3 个固定的知识文件，再执行更新。")
    else:
        validation_errors = validate_uploaded_files(uploaded_files)

        if validation_errors:
            for error_message in validation_errors:
                st.error(error_message)
        else:
            try:
                file_snapshots = build_uploaded_file_snapshots(uploaded_files)
                hash_record = load_hash_record()
                changed_files, unchanged_files, updated_hash_record = compare_uploaded_files(
                    file_snapshots,
                    hash_record,
                )

                # 没有任何文件变化时，直接结束更新，避免重复写入和重复处理。
                if not changed_files:
                    st.info("3 个知识文件内容均未变化，已跳过保存和重建。")

                    if unchanged_files:
                        st.write(f"未变化文件：{', '.join(unchanged_files)}")
                else:
                    changed_file_snapshots = [
                        snapshot
                        for snapshot in file_snapshots
                        if snapshot["name"] in changed_files
                    ]

                    # 只保存变化的文件，再调用后端知识库模块做真实读取验证。
                    save_uploaded_files(changed_file_snapshots)
                    st.write(f"已更新文件：{', '.join(changed_files)}")

                    if unchanged_files:
                        st.write(f"未变化文件：{', '.join(unchanged_files)}")

                    knowledge_docs = load_knowledge_files()
                    # 上传页继续往后走一步：把知识文件切成 chunk，确认离线处理链路已经打通。
                    knowledge_chunks = build_knowledge_chunks(knowledge_docs)
                    preview_text = build_preview_text(knowledge_docs)
                    chunk_preview_text = build_chunk_preview_text(knowledge_chunks)

                    # 只有知识处理成功后，才写入最新 MD5，避免失败时错误地跳过后续更新。
                    save_hash_record(updated_hash_record)

                    st.success("知识库文件上传成功，已完成基础读取验证。")
                    st.write(f"已成功加载 {len(knowledge_docs)} 个知识文件。")
                    st.write(f"已切分出 {len(knowledge_chunks)} 个文本块。")
                    st.subheader("知识文件预览")
                    st.code(preview_text, language="text")
                    st.subheader("示例文本块预览")
                    st.code(chunk_preview_text, language="text")
            except Exception as error:
                st.error(f"知识库更新失败：{error}")
