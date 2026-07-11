import re

from clothing_assistant.config_data import (
    CARE_KNOWLEDGE_FILE,
    COLOR_KNOWLEDGE_FILE,
    DATA_DIR,
    FIT_KNOWLEDGE_FILE,
    KNOWLEDGE_FILE_DOMAINS,
    KNOWLEDGE_FILES,
    MATERIAL_KNOWLEDGE_FILE,
    SCENE_KNOWLEDGE_FILE,
)


# 加载配置中的知识文件；缺少任一文件时拒绝重建，避免产生半完整索引。
def load_knowledge_files(data_dir=DATA_DIR, file_names=KNOWLEDGE_FILES):
    knowledge_docs = []
    missing_files = []

    for file_name in file_names:
        file_path = data_dir / file_name

        if not file_path.exists():
            missing_files.append(str(file_path))
            continue

        content = file_path.read_text(encoding="utf-8").strip()
        knowledge_docs.append(
            {
                "file_name": file_name,
                "file_path": str(file_path),
                "content": content,
            }
        )

    if missing_files:
        missing_text = "\n".join(missing_files)
        raise FileNotFoundError(f"以下知识文件不存在：\n{missing_text}")

    return knowledge_docs


# 默认切块策略：适合“尺码推荐.txt”这种一行就是一条完整规则的文件。
def split_lines_into_chunks(text):
    chunks = []

    # splitlines() 会按换行切开；strip() 用来去掉每行首尾空格。
    for line in text.splitlines():
        clean_line = line.strip()

        # 空行没有知识价值，先跳过，避免后面生成无意义的向量。
        if not clean_line:
            continue

        chunks.append(clean_line)

    return chunks


# 编号主题段必须整体保留，避免“适用场景”和“解释”被切成两个无上下文的向量。
def split_numbered_sections_into_chunks(text):
    """将编号标题及其说明保留为一个可检索的知识块。

    Args:
        text: 使用 ``1. 标题`` 作为主题边界的知识文件内容。

    Returns:
        每个编号主题及其后续说明组成的文本块列表。
    """
    chunks = []
    current_block = []
    section_header_pattern = re.compile(r"^\d+\.\s+")

    for line in text.splitlines():
        clean_line = line.strip()

        if not clean_line:
            continue

        if section_header_pattern.match(clean_line):
            if current_block:
                chunks.append("\n".join(current_block))

            current_block = [clean_line]
            continue

        if current_block:
            current_block.append(clean_line)
        else:
            current_block = [clean_line]

    if current_block:
        chunks.append("\n".join(current_block))

    return chunks


# 洗涤文件按“季节标题 + 材质块”切块，避免洗涤和养护说明被拆散。
def split_care_text_into_chunks(text):
    chunks = []
    current_section = None
    current_block = []
    section_header_pattern = re.compile(r"^[一二三四五六七八九十]+、")
    material_header_pattern = re.compile(r"^\d+\.\s+")

    def flush_current_block():
        if current_block:
            chunks.append("\n".join(current_block))
            current_block.clear()

    for line in text.splitlines():
        clean_line = line.strip()

        if not clean_line:
            continue

        if section_header_pattern.match(clean_line):
            flush_current_block()
            current_section = clean_line
            continue

        if material_header_pattern.match(clean_line):
            flush_current_block()

            if current_section:
                current_block.append(current_section)

            current_block.append(clean_line)
            continue

        if current_block:
            current_block.append(clean_line)
        elif current_section:
            current_block.extend([current_section, clean_line])
        else:
            current_block.append(clean_line)

    flush_current_block()

    return chunks


# 切分单个知识文件：按文件类型选择策略，而不是所有文件一律按行切。
def split_text_into_chunks(text, file_name):
    if file_name in {
        COLOR_KNOWLEDGE_FILE,
        SCENE_KNOWLEDGE_FILE,
        MATERIAL_KNOWLEDGE_FILE,
        FIT_KNOWLEDGE_FILE,
    }:
        return split_numbered_sections_into_chunks(text)

    if file_name == CARE_KNOWLEDGE_FILE:
        return split_care_text_into_chunks(text)

    return split_lines_into_chunks(text)


# 构建整个知识库的文本块：给每个 chunk 加上来源信息，方便后续检索和溯源。
def build_knowledge_chunks(knowledge_docs):
    """构建带来源和业务域元数据的知识块。

    domain 与原始文本一起进入向量索引，确保检索、评测和后续来源过滤
    使用同一份业务语义，而不是根据文件名重复推断。

    Args:
        knowledge_docs: 已从本地知识文件读取的文档字典列表。

    Returns:
        供向量索引写入的知识块字典列表。
    """
    knowledge_chunks = []

    for doc in knowledge_docs:
        text_chunks = split_text_into_chunks(doc["content"], doc["file_name"])

        for index, chunk_content in enumerate(text_chunks, start=1):
            knowledge_chunks.append(
                {
                    "chunk_id": f"{doc['file_name']}-{index:03d}",
                    "file_name": doc["file_name"],
                    "file_path": doc["file_path"],
                    # domain 让检索结果保留业务语义，后续可做来源过滤和评测分析。
                    "domain": KNOWLEDGE_FILE_DOMAINS.get(doc["file_name"], "general"),
                    "content": chunk_content,
                }
            )

    return knowledge_chunks

#为一组知识库文档（knowledge_docs）生成一段简短的预览文本。
def build_preview_text(knowledge_docs):
    preview_lines = []

    for doc in knowledge_docs:
        first_line = doc["content"].splitlines()[0] if doc["content"] else "(空文件)"
        preview_lines.append(f"{doc['file_name']} -> {first_line}")

    return "\n".join(preview_lines)


def main():
    knowledge_docs = load_knowledge_files()
    knowledge_chunks = build_knowledge_chunks(knowledge_docs)

    print(f"已成功加载 {len(knowledge_docs)} 个知识文件。")
    print(build_preview_text(knowledge_docs))
    print(f"已切分出 {len(knowledge_chunks)} 个文本块。")
    print("示例 chunk：")

    for chunk in knowledge_chunks[:5]:
        print(f"{chunk['chunk_id']} -> {chunk['content']}")


if __name__ == "__main__":
    main()
