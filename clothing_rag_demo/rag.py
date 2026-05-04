from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.messages import HumanMessage, SystemMessage

from config_data import (
    CARE_KNOWLEDGE_FILE,
    CHAT_MODEL_NAME,
    CHAT_TEMPERATURE,
    COLOR_KNOWLEDGE_FILE,
    DEFAULT_TEST_QUERY,
)
from size_matcher import has_complete_measurements, match_size_rule
from vector_stores import search_similar_chunks


COLOR_DAILY_WEAR_KEYWORDS = [
    "场合",
    "日常通勤",
    "基础色",
    "黑白灰",
    "米色",
    "藏蓝",
    "简约大气",
    "休闲场合",
]

CARE_TSHIRT_WASH_KEYWORDS = [
    "T恤",
    "洗涤",
    "机洗",
    "手洗",
    "水温",
    "中性洗涤剂",
    "浅色与深色分开洗",
    "深色分开洗",
    "晾晒",
    "收纳",
]


# 初始化聊天模型：最小版本只保留模型名和温度配置。
def get_chat_model():
    return ChatTongyi(
        model=CHAT_MODEL_NAME,
        temperature=CHAT_TEMPERATURE,
    )


def score_color_chunk_for_daily_wear(chunk):
    content = chunk["content"]
    return sum(1 for keyword in COLOR_DAILY_WEAR_KEYWORDS if keyword in content)


def rerank_color_chunks(color_chunks):
    return sorted(
        color_chunks,
        key=lambda chunk: (-score_color_chunk_for_daily_wear(chunk), chunk["score"]),
    )


def score_care_chunk_for_tshirt_wash(chunk):
    content = chunk["content"]
    return sum(1 for keyword in CARE_TSHIRT_WASH_KEYWORDS if keyword in content)


def rerank_care_chunks(care_chunks):
    return sorted(
        care_chunks,
        key=lambda chunk: (-score_care_chunk_for_tshirt_wash(chunk), chunk["score"]),
    )


# 把复合问题拆成“颜色”和“洗涤”两个子问题，再按来源文件做定向检索。
def retrieve_topic_chunks(user_query):
    color_query = (
        f"{user_query}。"
        "颜色选择，日常穿，日常通勤，场合，基础色，"
        "黑白灰，米色，藏蓝，简约大气。"
    )
    care_query = (
        f"{user_query}。"
        "T恤，洗涤，清洗，养护，机洗，手洗，水温，"
        "中性洗涤剂，浅色与深色分开洗，晾晒，收纳。"
    )

    color_chunks = search_similar_chunks(
        color_query,
        top_k=2,
        metadata_filter={"file_name": COLOR_KNOWLEDGE_FILE},
    )
    color_chunks = rerank_color_chunks(color_chunks)
    care_chunks = search_similar_chunks(
        care_query,
        top_k=4,
        metadata_filter={"file_name": CARE_KNOWLEDGE_FILE},
    )
    care_chunks = rerank_care_chunks(care_chunks)[:2]

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


# 把最近几轮聊天历史整理成 Prompt 文本，帮助模型理解“它、这个、宽松一点”等追问。
def format_chat_history(chat_history):
    if not chat_history:
        return "历史对话：当前没有历史对话。"

    history_sections = ["历史对话："]

    for index, chat_turn in enumerate(chat_history, start=1):
        history_sections.append(
            "\n".join(
                [
                    f"第{index}轮",
                    f"用户：{chat_turn['user_query']}",
                    f"助手：{chat_turn['assistant_answer']}",
                ]
            )
        )

    return "\n\n".join(history_sections)


def find_latest_history_user_query(chat_history):
    if not chat_history:
        return None

    # 只从历史里的用户原始问题取上下文，避免助手回答中的尺码规则文本污染当前判断。
    for chat_turn in reversed(chat_history):
        history_query = chat_turn.get("user_query", "").strip()

        if history_query:
            return history_query

    return None


def find_latest_history_user_query_with_measurements(chat_history):
    if not chat_history:
        return None

    # 追问缺少身高体重时，只回看历史里的用户问题，不从助手回答里抽取。
    for chat_turn in reversed(chat_history):
        history_query = chat_turn.get("user_query", "").strip()

        if history_query and has_complete_measurements(history_query):
            return history_query

    return None


def build_size_query(user_query, chat_history):
    if has_complete_measurements(user_query):
        # 当前问题已经给出新的身高体重时，当前事实优先，历史不能覆盖它。
        return user_query

    history_query = find_latest_history_user_query_with_measurements(chat_history)

    if not history_query:
        return user_query

    # 只有当前问题缺少身高体重时，才用上一轮用户问题补足尺码匹配上下文。
    return f"{history_query}\n当前追问：{user_query}"


def build_retrieval_query(user_query, chat_history):
    if has_complete_measurements(user_query):
        # 完整新问题通常已经包含衣服类型和场景，检索时不需要历史。
        return user_query

    history_query = find_latest_history_user_query(chat_history)

    if not history_query:
        return user_query

    # 短追问如“那洗的时候呢”需要上一轮用户问题里的 T恤、日常穿等上下文。
    return f"{history_query}\n当前追问：{user_query}"

# 组装混合方案 Prompt：尺码走规则模块，颜色和洗涤走检索，然后统一交给模型组织答案。
def build_rag_prompt(user_query, size_match, topic_chunks, chat_history=None):
    history_context = format_chat_history(chat_history)
    size_context = format_size_context(size_match)
    color_context = format_chunk_context("颜色参考资料", topic_chunks["color_chunks"])
    care_context = format_chunk_context("洗涤参考资料", topic_chunks["care_chunks"])

    return f"""
你是一个服装知识库问答助手。
请严格优先根据提供的规则匹配结果和参考资料回答问题，不要脱离知识库内容自由发挥。
如果参考资料中包含相关原则、适用场景、颜色范围、洗涤方式或注意事项，
你必须基于这些资料给出可执行建议。
只有当对应部分完全没有相关参考资料时，才说明“知识库中没有明确说明”。
历史对话只用于理解当前问题中的追问、省略和代词。
当前用户问题中明确给出的身高、体重、衣服类型和偏好优先级高于历史对话。
如果历史对话和知识库资料冲突，必须以知识库资料为准。

{history_context}

用户问题：
{user_query}

{size_context}

{color_context}

{care_context}

回答要求：
1. 使用中文回答。
2. 如果当前问题同时询问尺码、颜色、洗涤，按“尺码建议 / 颜色建议 / 洗涤建议”三个部分作答。
3. 如果当前问题是追问，只回答追问相关部分；不要重复当前问题没有问到的颜色或洗涤内容。
4. 如果尺码规则已给出主推荐和备选尺码，必须保留这个推荐关系，不要改写成其他尺码。
5. 如果匹配类型是 mixed，必须说明“身高和体重落在不同尺码区间”，不能说完全符合某一个尺码。
6. 颜色建议必须优先使用颜色参考资料中的场景、基础色、通勤色、休闲色信息。
7. 洗涤建议必须优先使用洗涤参考资料中的材质、洗涤方式、水温、晾晒、收纳信息。
8. 不要因为资料是原则性建议而拒答；原则性资料也可以转化成用户可执行的建议。
9. 只有对应参考资料完全无关时，才说“知识库中没有明确说明”。
""".strip()


# 执行一次混合式 RAG：尺码走规则匹配，颜色和洗涤走定向检索，最后统一生成答案。
def generate_answer(user_query, chat_history=None):
    size_query = build_size_query(user_query, chat_history)
    retrieval_query = build_retrieval_query(user_query, chat_history)
    size_match = match_size_rule(size_query)
    topic_chunks = retrieve_topic_chunks(retrieval_query)
    prompt = build_rag_prompt(user_query, size_match, topic_chunks, chat_history)
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
        "chat_history": chat_history or [],
        "size_query": size_query,
        "retrieval_query": retrieval_query,
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
