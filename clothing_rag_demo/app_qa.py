import streamlit as st
from requests.exceptions import RequestException

from config_data import DEFAULT_TEST_QUERY
from rag import generate_answer


st.set_page_config(
    page_title="服装知识库问答",
    layout="wide",
)


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


def render_chunks(title, chunks):
    st.subheader(title)

    if not chunks:
        st.info("没有检索到相关参考资料。")
        return

    for index, chunk in enumerate(chunks, start=1):
        with st.expander(f"{index}. {chunk['file_name']} | {chunk['chunk_id']}"):
            st.write(f"距离分数：{chunk['score']:.4f}")
            st.code(chunk["content"], language="text")


st.title("服装知识库问答")

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
                result = generate_answer(clean_query)
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

        with st.expander("尺码规则匹配"):
            render_size_match(result["size_match"])

        render_chunks("颜色参考资料", result["topic_chunks"]["color_chunks"])
        render_chunks("洗涤参考资料", result["topic_chunks"]["care_chunks"])
