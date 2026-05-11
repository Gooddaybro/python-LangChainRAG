import streamlit as st
from requests.exceptions import RequestException

from clothing_rag_demo.agent.agent_executor import run_agent
from clothing_rag_demo.config_data import DEFAULT_TEST_QUERY
from clothing_rag_demo.file_history_store import (
    append_chat_turn,
    clear_chat_history,
    load_chat_history,
)
from clothing_rag_demo.rag import generate_answer

# 负责页面输入和展示
# 页面配置
st.set_page_config(
    page_title="服装知识库问答",
    layout="wide",
)

# 展示尺码规则匹配结果
def render_size_match(size_match):
    if not size_match:
        st.info("未返回尺码规则匹配结果。")
        return

    st.write(f"匹配类型：{size_match['match_type']}")
    st.write(f"主推荐尺码：{size_match['primary_size']}")

    if size_match["alternative_size"]:
        st.write(f"备选尺码：{size_match['alternative_size']}")

    st.write(f"推荐理由：{size_match['reason']}")

    if size_match["matched_rule"]:
        st.code(size_match["matched_rule"], language="text")

    if size_match["alternative_rule"]:
        st.write("备选规则：")
        st.code(size_match["alternative_rule"], language="text")

# 返回的结构化结果可视化
def render_chunks(title, chunks):
    st.subheader(title)

    if not chunks:
        st.info("没有检索到相关参考资料。")
        return

    for index, chunk in enumerate(chunks, start=1):
        with st.expander(f"{index}. {chunk['file_name']} | {chunk['chunk_id']}"):
            st.write(f"距离分数：{chunk['score']:.4f}")
            st.code(chunk["content"], language="text")


# 展示本次提交时实际传给 RAG 的最近历史，方便观察多轮对话是否生效。
def render_chat_history(chat_history):
    if not chat_history:
        st.info("本次没有使用历史对话。")
        return

    for index, chat_turn in enumerate(chat_history, start=1):
        st.write(f"第 {index} 轮")
        st.write(f"用户：{chat_turn['user_query']}")
        st.write(f"助手：{chat_turn['assistant_answer']}")


# 展示 RAG 内部实际使用的输入，方便排查历史是否污染当前问题。
def render_debug_queries(result):
    st.write("尺码匹配实际输入：")
    st.code(result["size_query"], language="text")

    st.write("向量检索实际输入：")
    st.code(result["retrieval_query"], language="text")


def render_agent_debug(debug):
    st.write(f"用户问题：{debug['user_query']}")
    st.write("意图判断：")
    st.json(debug["intent_result"])

    st.write("调用工具：")
    st.json(debug["selected_tools"])

    st.write("使用的历史信息：")
    st.json(debug["used_history"])
    st.write(f"历史处理说明：{debug['ignored_history_reason']}")

    if debug["retrieval_query"]:
        st.write("检索输入：")
        st.code(debug["retrieval_query"], language="text")

    render_chunks("Agent 检索资料", debug["retrieved_chunks"])

    st.write("工具结果：")
    st.json(debug["tool_results"])

    st.write("最终 Prompt：")
    st.code(debug["final_prompt"], language="text")


# 主界面
st.title("服装知识库问答")

if st.button("清空聊天历史"):
    clear_chat_history()
    st.success("聊天历史已清空。")

use_agent = st.checkbox("启用导购 Agent", value=False)

query = st.text_area(
    "请输入服装相关问题",
    value=DEFAULT_TEST_QUERY,
    height=110,
)

if st.button("提交问题", type="primary"):
    clean_query = query.strip()

    if not clean_query:
        st.error("问题不能为空。")
    else:
        try:
            with st.spinner("正在检索知识库并生成答案..."):
                # 先读取最近 3 轮历史，让 RAG 能理解“宽松一点”等追问。
                chat_history = load_chat_history(limit=3)

                if use_agent:
                    result = run_agent(clean_query, chat_history=chat_history)
                else:
                    result = generate_answer(clean_query, chat_history=chat_history)

                # 只有答案成功生成后才写入历史，避免把失败请求或错误信息保存进去。
                append_chat_turn(clean_query, result["answer"])
        except FileNotFoundError as error:
            st.error("知识库文件不存在，请先上传知识文件并完成向量库重建。")
            st.code(str(error), language="text")
            st.stop()
        except RequestException as error:
            st.error("模型接口连接失败，请检查网络、代理或 API Key 后重启问答页面。")
            st.code(str(error), language="text")
            st.stop()
        except Exception as error:
            # 这里保留兜底提示，避免页面直接暴露整屏 Traceback。
            st.error("问答流程执行失败，请根据下面的错误信息定位是向量检索、模型调用还是业务代码问题。")
            st.code(str(error), language="text")
            st.stop()

        st.subheader("回答")
        st.write(result["answer"])

        if use_agent:
            with st.expander("Agent Debug"):
                render_agent_debug(result["debug"])
        else:
            with st.expander("本次使用的聊天历史"):
                render_chat_history(result["chat_history"])

            with st.expander("本次调试信息"):
                render_debug_queries(result)

            with st.expander("尺码规则匹配"):
                render_size_match(result["size_match"])

            render_chunks("颜色参考资料", result["topic_chunks"]["color_chunks"])
            render_chunks("洗涤参考资料", result["topic_chunks"]["care_chunks"])
