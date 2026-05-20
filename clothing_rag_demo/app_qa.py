import streamlit as st
from requests.exceptions import RequestException

from clothing_rag_demo.agent.agent_executor import run_agent
from clothing_rag_demo.agent.eval_report import build_eval_report
from clothing_rag_demo.agent.langgraph_executor import run_langgraph_agent
from clothing_rag_demo.config_data import DEFAULT_TEST_QUERY, PROJECT_DISPLAY_NAME
from clothing_rag_demo.file_history_store import (
    append_chat_turn,
    clear_chat_history,
    load_chat_history,
)


LANGGRAPH_MODE = "LangGraph 主线"
PIPELINE_MODE = "Pipeline 对照"


def run_selected_agent(
    execution_mode,
    clean_query,
    chat_history,
    pipeline_runner=run_agent,
    langgraph_runner=run_langgraph_agent,
):
    """根据页面选择运行 LangGraph 主线或旧 Pipeline 对照。"""
    if execution_mode == LANGGRAPH_MODE:
        return langgraph_runner(clean_query, chat_history=chat_history)

    return pipeline_runner(clean_query, chat_history=chat_history)


def build_status_summary(execution_mode, debug):
    """从统一 debug 结构中提取页面顶部状态指标。"""
    return {
        "execution_mode": execution_mode,
        "intent": debug.get("intent_result", {}).get("intent", "未运行"),
        "tool_count": len(debug.get("selected_tools", [])),
        "stop_reason": debug.get("stop_reason", "未运行"),
        "rag_chunk_count": len(debug.get("retrieved_chunks", [])),
    }


def build_page_hero_html():
    return f"""
        <div class="agent-hero">
            <h1>{PROJECT_DISPLAY_NAME}</h1>
            <p>LangGraph 主线与 Pipeline 对照的本地调试控制台</p>
        </div>
        """


def format_tools_for_page(tools):
    return ", ".join(tools) if tools else "-"


def format_pass_for_page(value):
    return "PASS" if value else "FAIL"


def build_eval_tables(report):
    """把 eval report 的内部结构转换成 Streamlit 表格友好的行。"""
    summary = {
        "Cases": report["summary"]["case_count"],
        "Passed Rows": report["summary"]["pass_count"],
        "Failed Rows": report["summary"]["failed_count"],
        "Consistent Cases": report["summary"]["consistent_case_count"],
        "Inconsistent Cases": report["summary"]["inconsistent_case_count"],
    }
    result_rows = [
        {
            "Case": row["case"],
            "Executor": row["executor"],
            "Intent": row["actual_intent"],
            "Tools": format_tools_for_page(row["actual_tools"]),
            "Stop Reason": row["actual_stop_reason"],
            "RAG Chunks": row["rag_chunk_count"],
            "Pass": format_pass_for_page(row["passed"]),
        }
        for row in report["rows"]
    ]
    consistency_rows = [
        {
            "Case": row["case"],
            "Consistent": format_pass_for_page(row["consistent"]),
            "Intent Variants": row["intent_count"],
            "Tool Variants": row["tools_count"],
            "Stop Variants": row["stop_reason_count"],
            "RAG Count Variants": row["rag_chunk_count_variants"],
        }
        for row in report["consistency_rows"]
    ]
    return summary, result_rows, consistency_rows


def apply_workbench_style():
    st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(135deg, #121212 0%, #1b1b1b 48%, #10201f 100%);
            color: #e5e7eb;
        }
        .block-container {
            padding-top: 2rem;
            max-width: 1280px;
        }
        [data-testid="stMetric"] {
            background: rgba(15, 23, 42, 0.72);
            border: 1px solid rgba(148, 163, 184, 0.24);
            border-radius: 8px;
            padding: 0.75rem 0.9rem;
        }
        .agent-hero {
            border: 1px solid rgba(45, 212, 191, 0.35);
            border-radius: 8px;
            padding: 1rem 1.15rem;
            background: rgba(15, 23, 42, 0.78);
            box-shadow: 0 16px 40px rgba(0, 0, 0, 0.24);
            margin-bottom: 1rem;
        }
        .agent-hero h1 {
            margin: 0;
            font-size: 2rem;
            letter-spacing: 0;
        }
        .agent-hero p {
            margin: 0.35rem 0 0;
            color: #cbd5e1;
        }
        .status-chip {
            display: inline-block;
            margin: 0 0.4rem 0.4rem 0;
            padding: 0.28rem 0.58rem;
            border-radius: 999px;
            background: rgba(14, 165, 233, 0.16);
            border: 1px solid rgba(56, 189, 248, 0.38);
            color: #e0f2fe;
            font-size: 0.86rem;
        }
        .answer-panel {
            border-left: 3px solid #2dd4bf;
            padding: 0.9rem 1rem;
            background: rgba(15, 23, 42, 0.66);
            border-radius: 8px;
            margin-bottom: 1rem;
        }
        .trace-step {
            padding: 0.55rem 0.75rem;
            margin-bottom: 0.45rem;
            border-radius: 8px;
            border: 1px solid rgba(148, 163, 184, 0.22);
            background: rgba(30, 41, 59, 0.72);
        }
        .trace-step strong {
            color: #5eead4;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_status_summary(summary):
    columns = st.columns(5)
    columns[0].metric("执行模式", summary["execution_mode"])
    columns[1].metric("意图", summary["intent"])
    columns[2].metric("工具数", summary["tool_count"])
    columns[3].metric("停止原因", summary["stop_reason"])
    columns[4].metric("RAG 资料", summary["rag_chunk_count"])


def render_status_chips(debug):
    tools = format_tools_for_page(debug.get("selected_tools", []))
    retrieval_query = debug.get("retrieval_query") or "-"
    chips = [
        f"intent: {debug.get('intent_result', {}).get('intent', '-')}",
        f"tools: {tools}",
        f"stop: {debug.get('stop_reason') or '-'}",
        f"retrieval: {retrieval_query}",
    ]
    st.markdown(
        "".join(f'<span class="status-chip">{chip}</span>' for chip in chips),
        unsafe_allow_html=True,
    )


def render_trace_timeline(trace_events):
    if not trace_events:
        st.info("本次没有 trace 事件。")
        return

    for index, event in enumerate(trace_events, start=1):
        st.markdown(
            f"""
            <div class="trace-step">
                <strong>{index}. {event["step"]}</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.json(event.get("data", {}))

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


def render_agent_debug(debug):
    trace_tab, tools_tab, chunks_tab, prompt_tab = st.tabs(
        ["Trace Timeline", "Tool Results", "Retrieved Chunks", "Final Prompt"]
    )

    with trace_tab:
        st.write(f"用户问题：{debug['user_query']}")
        st.write("意图判断：")
        st.json(debug["intent_result"])
        st.write("使用的历史信息：")
        st.json(debug["used_history"])
        st.write(f"历史处理说明：{debug['ignored_history_reason']}")
        render_trace_timeline(debug.get("trace_events", []))

    with tools_tab:
        st.write("调用工具：")
        st.json(debug["selected_tools"])
        st.write("缺信息检查：")
        st.json(debug.get("missing_info_result", {}))
        st.write("结构化查询结果：")
        st.json(debug.get("structured_result", {}))
        st.write("答案校验：")
        st.json(debug.get("validation_result", {}))
        st.write("证据摘要：")
        st.json(debug.get("evidence_summary", {}))
        st.write("工具结果：")
        st.json(debug["tool_results"])

    with chunks_tab:
        if debug["retrieval_query"]:
            st.write("检索输入：")
            st.code(debug["retrieval_query"], language="text")
        render_chunks("Accepted Chunks", debug.get("accepted_chunks", debug["retrieved_chunks"]))
        render_chunks("Rejected Chunks", debug.get("rejected_chunks", []))

    with prompt_tab:
        st.code(debug["final_prompt"], language="text")


def render_eval_report_panel():
    with st.expander("Eval Report", expanded=False):
        if st.button("运行 Eval Report"):
            try:
                report = build_eval_report()
                summary, result_rows, consistency_rows = build_eval_tables(report)
            except Exception as error:
                st.error("Eval Report 执行失败。")
                st.code(str(error), language="text")
                return

            metric_columns = st.columns(5)
            metric_items = list(summary.items())
            for column, (label, value) in zip(metric_columns, metric_items):
                column.metric(label, value)

            st.subheader("Executor Results")
            st.dataframe(result_rows, use_container_width=True, hide_index=True)

            st.subheader("Executor Consistency")
            st.dataframe(consistency_rows, use_container_width=True, hide_index=True)


def main():
    st.set_page_config(
        page_title=PROJECT_DISPLAY_NAME,
        layout="wide",
    )
    apply_workbench_style()

    st.markdown(build_page_hero_html(), unsafe_allow_html=True)

    if "last_agent_result" not in st.session_state:
        st.session_state["last_agent_result"] = None
        st.session_state["last_execution_mode"] = LANGGRAPH_MODE

    control_column, answer_column = st.columns([0.9, 1.4])

    with control_column:
        execution_mode = st.radio(
            "执行模式",
            [LANGGRAPH_MODE, PIPELINE_MODE],
            horizontal=True,
            key="execution_mode",
        )

        query = st.text_area(
            "请输入服装相关问题",
            value=DEFAULT_TEST_QUERY,
            height=145,
        )

        submit_column, clear_column = st.columns([1, 1])
        submit_clicked = submit_column.button("提交问题", type="primary", use_container_width=True)

        if clear_column.button("清空历史", use_container_width=True):
            clear_chat_history()
            st.session_state["last_agent_result"] = None
            st.success("聊天历史已清空。")

    if submit_clicked:
        clean_query = query.strip()

        if not clean_query:
            st.error("问题不能为空。")
        else:
            try:
                with st.spinner("Agent 正在调度工具并生成答案..."):
                    # 先读取最近 3 轮历史，让 Agent 能理解“宽松一点”等追问。
                    chat_history = load_chat_history(limit=3)
                    result = run_selected_agent(
                        execution_mode,
                        clean_query,
                        chat_history=chat_history,
                    )

                    # 只有答案成功生成后才写入历史，避免把失败请求或错误信息保存进去。
                    append_chat_turn(clean_query, result["answer"])
                    st.session_state["last_agent_result"] = result
                    st.session_state["last_execution_mode"] = execution_mode
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

    result = st.session_state["last_agent_result"]
    active_mode = st.session_state["last_execution_mode"]

    with answer_column:
        if result:
            debug = result["debug"]
            render_status_summary(build_status_summary(active_mode, debug))
            st.subheader("回答")
            st.markdown(
                f'<div class="answer-panel">{result["answer"]}</div>',
                unsafe_allow_html=True,
            )
            render_status_chips(debug)
        else:
            render_status_summary(
                {
                    "execution_mode": execution_mode,
                    "intent": "未运行",
                    "tool_count": 0,
                    "stop_reason": "未运行",
                    "rag_chunk_count": 0,
                }
            )
            st.info("提交问题后，这里会显示 Agent 回答和状态。")

    if result:
        st.subheader("Agent Debug")
        render_agent_debug(result["debug"])

    render_eval_report_panel()


if __name__ == "__main__":
    main()
