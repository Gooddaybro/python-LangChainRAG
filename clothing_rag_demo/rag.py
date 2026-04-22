import re

from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.messages import HumanMessage, SystemMessage

from config_data import (
    CARE_KNOWLEDGE_FILE,
    CHAT_MODEL_NAME,
    CHAT_TEMPERATURE,
    COLOR_KNOWLEDGE_FILE,
    DEFAULT_TEST_QUERY,
    SIZE_KNOWLEDGE_FILE,
)
from knowledge_base import load_knowledge_files
from vector_stores import search_similar_chunks


# 初始化聊天模型：最小版本只保留模型名和温度配置。
def get_chat_model():
    return ChatTongyi(
        model=CHAT_MODEL_NAME,
        temperature=CHAT_TEMPERATURE,
    )


# 从用户问题里提取身高和体重，体重统一换算成“斤”，后面才方便和尺码规则做区间匹配。
def extract_user_measurements(user_query):
    height_match = re.search(r"身高\s*([0-9]{2,3}(?:\.\d+)?)\s*(?:cm|厘米)?", user_query, re.IGNORECASE)
    weight_match = re.search(
        r"体重\s*([0-9]{2,3}(?:\.\d+)?)\s*(kg|公斤|斤)?",
        user_query,
        re.IGNORECASE,
    )

    height_cm = float(height_match.group(1)) if height_match else None
    weight_value = float(weight_match.group(1)) if weight_match else None
    weight_unit = weight_match.group(2).lower() if weight_match and weight_match.group(2) else None

    if weight_value is None:
        weight_jin = None
    elif weight_unit in {"kg", "公斤"}:
        weight_jin = weight_value * 2
    else:
        # 当前业务里如果没有单位，默认按“斤”理解，避免尺码规则完全失效。
        weight_jin = weight_value

    return {
        "height_cm": height_cm,
        "weight_jin": weight_jin,
        "raw_weight_value": weight_value,
        "raw_weight_unit": weight_unit,
    }


# 解析单条尺码规则，输出统一结构；这样后面匹配时不用再反复写正则。
def parse_size_rule_line(line):
    pattern = re.compile(
        r"身高[:：]\s*(\d+)(?:-(\d+))?cm(\+)?[，,\s]*"
        r"体重[:：]\s*(\d+)(?:-(\d+))?\s*斤(\+)?[，,\s]*"
        r"建议尺码\s*([A-Za-z0-9]+)",
    )
    match = pattern.search(line)

    if not match:
        return None

    height_min = float(match.group(1))
    height_max = None if match.group(3) else float(match.group(2) or match.group(1))
    weight_min = float(match.group(4))
    weight_max = None if match.group(6) else float(match.group(5) or match.group(4))

    return {
        "rule_text": line,
        "height_min": height_min,
        "height_max": height_max,
        "weight_min": weight_min,
        "weight_max": weight_max,
        "size": match.group(7),
    }


def value_in_range(value, min_value, max_value):
    if value is None:
        return False

    if value < min_value:
        return False

    if max_value is not None and value > max_value:
        return False

    return True


# 尺码问题走规则匹配，不走纯向量检索；这是当前服装场景里最稳的做法。
def match_size_rule(user_query):
    measurements = extract_user_measurements(user_query)
    knowledge_docs = load_knowledge_files()
    size_doc = next(
        (doc for doc in knowledge_docs if doc["file_name"] == SIZE_KNOWLEDGE_FILE),
        None,
    )

    if not size_doc:
        return None

    for line in size_doc["content"].splitlines():
        clean_line = line.strip()

        if not clean_line:
            continue

        parsed_rule = parse_size_rule_line(clean_line)

        if not parsed_rule:
            continue

        height_ok = value_in_range(
            measurements["height_cm"],
            parsed_rule["height_min"],
            parsed_rule["height_max"],
        )
        weight_ok = value_in_range(
            measurements["weight_jin"],
            parsed_rule["weight_min"],
            parsed_rule["weight_max"],
        )

        if height_ok and weight_ok:
            return {
                "file_name": SIZE_KNOWLEDGE_FILE,
                "content": parsed_rule["rule_text"],
                "recommended_size": parsed_rule["size"],
                "measurements": measurements,
            }

    return None


# 把复合问题拆成“颜色”和“洗涤”两个子问题，再按来源文件做定向检索，避免被尺码文本淹没。
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
    if not size_match:
        return "尺码规则匹配结果：知识库中没有找到明确匹配的尺码规则。"

    measurements = size_match["measurements"]
    return "\n".join(
        [
            "尺码规则匹配结果：",
            f"用户身高：{measurements['height_cm']} cm",
            f"用户体重：{measurements['weight_jin']} 斤",
            f"命中规则：{size_match['content']}",
            f"推荐尺码：{size_match['recommended_size']}",
        ]
    )


# 组装混合方案 Prompt：尺码走规则，颜色和洗涤走检索，然后统一交给模型组织成自然语言答案。
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
3. 如果尺码规则已明确命中，优先直接使用该尺码，不要改写成其他尺码。
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

    if result["size_match"]:
        print(result["size_match"]["content"])
        print(f"推荐尺码：{result['size_match']['recommended_size']}")
    else:
        print("未命中明确尺码规则。")

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
