from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.messages import HumanMessage, SystemMessage

from config_data import (
    CARE_KNOWLEDGE_FILE,
    CHAT_MODEL_NAME,
    CHAT_TEMPERATURE,
    COLOR_KNOWLEDGE_FILE,
    DEFAULT_TEST_QUERY,
)
from size_matcher import match_size_rule
from vector_stores import search_similar_chunks


# 初始化聊天模型：最小版本只保留模型名和温度配置。
def get_chat_model():
    return ChatTongyi(
        model=CHAT_MODEL_NAME,
        temperature=CHAT_TEMPERATURE,
    )


# 把复合问题拆成“颜色”和“洗涤”两个子问题，再按来源文件做定向检索。
def retrieve_topic_chunks(user_query):
    color_query = f"{user_query}。请只关注颜色推荐和日常穿搭颜色选择。"
    care_query = f"{user_query}。请只关注洗涤养护和清洗注意事项。"

    color_chunks = search_similar_chunks(
        color_query,
        top_k=2,
        metadata_filter={"file_name": COLOR_KNOWLEDGE_FILE},
    )
    care_chunks = search_similar_chunks(
        care_query,
        top_k=2,
        metadata_filter={"file_name": CARE_KNOWLEDGE_FILE},
    )

    return {
        "color_chunks": color_chunks,
        "care_chunks": care_chunks,
    }


def format_chunk_context(title, chunks):
    if not chunks:
        return f"{title}：当前没有检索到可用资料。"

    context_sections = [f"{title}："]

    for index, chunk in enumerate(chunks, start=1):
        context_sections.append(
            "\n".join(
                [
                    f"资料{index}",
                    f"来源文件：{chunk['file_name']}",
                    f"文本块编号：{chunk['chunk_id']}",
                    f"内容：{chunk['content']}",
                ]
            )
        )

    return "\n\n".join(context_sections)


def format_size_context(size_match):
    if not size_match or not size_match["matched"]:
        reason = size_match["reason"] if size_match else "知识库中没有找到明确匹配的尺码规则。"
        return f"尺码规则匹配结果：{reason}"

    measurements = size_match["measurements"]
    lines = [
        "尺码规则匹配结果：",
        f"匹配类型：{size_match['match_type']}",
        f"用户身高：{measurements['height_cm']} cm",
        f"用户体重：{measurements['weight_jin']} 斤",
        f"主推荐尺码：{size_match['primary_size']}",
        f"推荐理由：{size_match['reason']}",
    ]

    if size_match["alternative_size"]:
        lines.append(f"备选尺码：{size_match['alternative_size']}")

    if size_match["matched_rule"]:
        lines.append(f"命中规则：{size_match['matched_rule']}")

    if size_match["alternative_rule"]:
        lines.append(f"备选规则：{size_match['alternative_rule']}")

    return "\n".join(lines)


# 组装混合方案 Prompt：尺码走规则模块，颜色和洗涤走检索，然后统一交给模型组织答案。
def build_rag_prompt(user_query, size_match, topic_chunks):
    size_context = format_size_context(size_match)
    color_context = format_chunk_context("颜色参考资料", topic_chunks["color_chunks"])
    care_context = format_chunk_context("洗涤参考资料", topic_chunks["care_chunks"])

    return f"""
你是一个服装知识库问答助手。
请严格优先根据提供的规则匹配结果和参考资料回答问题，不要脱离知识库内容自由发挥。
如果某一项资料不足，请明确说明“知识库中没有明确说明”。

用户问题：
{user_query}

{size_context}

{color_context}

{care_context}

回答要求：
1. 使用中文回答。
2. 必须按“尺码建议 / 颜色建议 / 洗涤建议”三个部分作答。
3. 如果尺码规则已给出主推荐和备选尺码，必须保留这个推荐关系，不要改写成其他尺码。
4. 如果颜色或洗涤资料不足，就明确说明知识库中没有明确说明。
""".strip()


# 执行一次混合式 RAG：尺码走规则匹配，颜色和洗涤走定向检索，最后统一生成答案。
def generate_answer(user_query):
    size_match = match_size_rule(user_query)
    topic_chunks = retrieve_topic_chunks(user_query)
    prompt = build_rag_prompt(user_query, size_match, topic_chunks)
    chat_model = get_chat_model()

    messages = [
        SystemMessage(content="你必须基于提供的规则匹配结果和知识库资料回答服装相关问题。"),
        HumanMessage(content=prompt),
    ]
    response = chat_model.invoke(messages)

    return {
        "query": user_query,
        "size_match": size_match,
        "topic_chunks": topic_chunks,
        "prompt": prompt,
        "answer": response.content,
    }


def main():
    result = generate_answer(DEFAULT_TEST_QUERY)

    print(f"测试问题：{result['query']}")
    print("尺码规则匹配结果：")

    size_match = result["size_match"]
    print(f"匹配类型：{size_match['match_type']}")
    print(f"主推荐尺码：{size_match['primary_size']}")
    print(f"备选尺码：{size_match['alternative_size']}")
    print(f"推荐理由：{size_match['reason']}")
    print(f"命中规则：{size_match['matched_rule']}")

    print("-" * 60)
    print("颜色检索结果：")

    for index, chunk in enumerate(result["topic_chunks"]["color_chunks"], start=1):
        print(f"[{index}] {chunk['file_name']} | {chunk['chunk_id']} | score: {chunk['score']:.4f}")
        print(chunk["content"])
        print("-" * 60)

    print("洗涤检索结果：")

    for index, chunk in enumerate(result["topic_chunks"]["care_chunks"], start=1):
        print(f"[{index}] {chunk['file_name']} | {chunk['chunk_id']} | score: {chunk['score']:.4f}")
        print(chunk["content"])
        print("-" * 60)

    print("最终答案：")
    print(result["answer"])


if __name__ == "__main__":
    main()
