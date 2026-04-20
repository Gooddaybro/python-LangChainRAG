# 管理员上传 3 份服装知识文件，并把它们保存到 data/ 目录。

from collections import Counter

import streamlit as st

from config_data import DATA_DIR, KNOWLEDGE_FILES
from knowledge_base import build_preview_text, load_knowledge_files


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


# 保存上传文件：通过校验后再覆盖写入 data/，这一步才算真正更新知识文件。
def save_uploaded_files(uploaded_files, target_dir=DATA_DIR):
    target_dir.mkdir(parents=True, exist_ok=True)

    for uploaded_file in uploaded_files:
        target_path = target_dir / uploaded_file.name
        target_path.write_bytes(uploaded_file.getvalue())


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
                # 先保存到 data/，再调用后端知识库模块做真实读取验证。
                save_uploaded_files(uploaded_files)
                knowledge_docs = load_knowledge_files()
                preview_text = build_preview_text(knowledge_docs)

                st.success("知识库文件上传成功，已完成基础读取验证。")
                st.write(f"已成功加载 {len(knowledge_docs)} 个知识文件。")
                st.code(preview_text, language="text")
            except Exception as error:
                st.error(f"知识库更新失败：{error}")
