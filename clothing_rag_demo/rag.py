from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.messages import HumanMessage, SystemMessage

from config_data import CHAT_MODEL_NAME, CHAT_TEMPERATURE, DEFAULT_TEST_QUERY, DEFAULT_TOP_K
from vector_stores import search_similar_chunks


# 初始化聊天模型：最小版本只保留模型名和温度配置。
def get_chat_model():
    return ChatTongyi(
        model=CHAT_MODEL_NAME,
        temperature=CHAT_TEMPERATURE,
    )


# 把检索到的知识块整理成可直接放入 Prompt 的参考资料文本。
def format_context(matched_chunks):
    if not matched_chunks:
        return "当前没有检索到可用的知识库资料。"

    context_sections = []

    for index, chunk in enumerate(matched_chunks, start=1):
        context_sections.append(
            "\n".join(
                [
                    f"参考资料{index}",
                    f"来源文件：{chunk['file_name']}",
                    f"文本块编号：{chunk['chunk_id']}",
                    f"内容：{chunk['content']}",
                ]
            )
        )

    return "\n\n".join(context_sections)


# 组装最小 RAG Prompt：明确要求模型必须优先依据知识库资料作答，避免自由发挥。
def build_rag_prompt(user_query, matched_chunks):
    context_text = format_context(matched_chunks)

    return f"""
你是一个服装知识库问答助手。
请严格优先根据提供的参考资料回答问题，不要脱离知识库内容自由发挥。
如果参考资料无法直接支持答案，请明确说明“知识库中没有明确说明”。

用户问题：
{user_query}

参考资料：
{context_text}

回答要求：
1. 使用中文回答。
2. 先直接给出结论，再补充理由。
3. 如果问题同时涉及尺码、颜色、洗涤，请分点回答。
""".strip()


# 执行一次最小 RAG 闭环：检索知识块 -> 构造 Prompt -> 调模型生成答案。
def generate_answer(user_query, top_k=DEFAULT_TOP_K):
    matched_chunks = search_similar_chunks(user_query, top_k=top_k)
    prompt = build_rag_prompt(user_query, matched_chunks)
    chat_model = get_chat_model()

    messages = [
        SystemMessage(content="你必须基于提供的知识库资料回答服装相关问题。"),
        HumanMessage(content=prompt),
    ]
    response = chat_model.invoke(messages)

    return {
        "query": user_query,
        "matched_chunks": matched_chunks,
        "prompt": prompt,
        "answer": response.content,
    }


def main():
    result = generate_answer(DEFAULT_TEST_QUERY)

    print(f"测试问题：{result['query']}")
    print("检索到的参考资料：")

    for index, chunk in enumerate(result["matched_chunks"], start=1):
        print(
            f"[{index}] 文件: {chunk['file_name']} | chunk: {chunk['chunk_id']} | "
            f"score: {chunk['score']:.4f}"
        )
        print(chunk["content"])
        print("-" * 60)

    print("最终答案：")
    print(result["answer"])


if __name__ == "__main__":
    main()
