from config_data import DATA_DIR, KNOWLEDGE_FILES


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


def build_preview_text(knowledge_docs):
    preview_lines = []

    for doc in knowledge_docs:
        first_line = doc["content"].splitlines()[0] if doc["content"] else "(空文件)"
        preview_lines.append(f"{doc['file_name']} -> {first_line}")

    return "\n".join(preview_lines)


def main():
    knowledge_docs = load_knowledge_files()
    print(f"已成功加载 {len(knowledge_docs)} 个知识文件。")
    print(build_preview_text(knowledge_docs))


if __name__ == "__main__":
    main()
