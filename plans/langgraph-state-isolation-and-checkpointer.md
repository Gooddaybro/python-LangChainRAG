# 修复方案：LangGraph 状态隔离与请求级 Graph

## 上下文

根据 Obsidian 笔记《AI服装导购项目LangGraph状态泄漏检查与优化建议》的检查结果，项目已经通过 `build_initial_state` 显式重置单轮字段，预防了上一轮 `stop_reason`、`answer`、`tool_results` 等状态污染下一轮请求。

但当前仍有三个需要治理的问题：

1. `run_langgraph_agent()` 默认可能使用全局 cached graph，API 请求和 debug graph 职责混在一起。
2. 直接调用 `run_langgraph_agent()` 时，如果只传 `session_id` 不传 `thread_id`，仍会生成随机 thread id，不利于多轮调试。
3. `AgentState` 使用 `TypedDict(total=False)`，新增字段后容易忘记在初始 state 中清空。

## 当前判断

不要直接删除 `get_default_langgraph_agent()`。

它仍然有价值：

- `langgraph.json` 需要默认图入口。
- LangGraph Studio / 本地 debug 需要 cached graph。
- checkpoint history 回放需要稳定 graph + checkpointer。

更合理的做法是区分两个入口：

```text
get_default_langgraph_agent()
  -> debug / Studio / local replay cached graph

run_langgraph_agent()
  -> API 默认 request-scoped graph
```

## 修复 1：新增 thread_id 解析函数

**文件：** `clothing_assistant/agent/langgraph_executor.py`

新增：

```python
def resolve_thread_id(thread_id=None, session_id=None):
    if thread_id:
        return thread_id

    if session_id:
        return session_id

    return generate_thread_id()
```

优先级：

```text
thread_id > session_id > generate_thread_id()
```

本轮不把 `user_id` 拼进 thread id。原因是 Java/Python 合同已经定义了 `thread_id/session_id` 的含义，第一阶段不改变对外 debug 语义。

## 修复 2：run_langgraph_agent 默认使用 request-scoped graph

**文件：** `clothing_assistant/agent/langgraph_executor.py`

保留：

```python
get_default_langgraph_agent()
```

但只作为 debug / Studio cached graph。

修改 `run_langgraph_agent()`：

```python
def run_langgraph_agent(..., use_cached_graph=False):
    resolved_thread_id = resolve_thread_id(thread_id, session_id)

    if use_cached_graph and should_use_default_graph(tool_registry, answer_generator, max_tool_calls):
        graph = get_default_langgraph_agent()
    else:
        graph = build_langgraph_agent(
            tool_registry=tool_registry,
            answer_generator=answer_generator,
            max_tool_calls=max_tool_calls,
            checkpointer=InMemorySaver(),
        )
```

这样：

- API 默认每次请求独立 graph/checkpointer。
- debug 或测试需要 cached graph 时显式传 `use_cached_graph=True`。
- `get_default_langgraph_agent()` 不被删除，`langgraph.json` 不受影响。

## 修复 3：抽出单轮状态默认值

**文件：** `clothing_assistant/agent/langgraph_executor.py`

新增：

```python
def build_run_state_defaults():
    return {
        "intent_result": {},
        "memory_result": {},
        "agent_query": "",
        "missing_info_result": {},
        "structured_result": {},
        "accepted_chunks": [],
        "rejected_chunks": [],
        "retrieval_route": {},
        "draft_answer": "",
        "validation_result": {},
        "fallback_result": {},
        "evidence_summary": {},
        "selected_tools": [],
        "tool_call_count": 0,
        "tool_results": {},
        "generation_attempts": 0,
        "max_generation_attempts": 2,
        "validation_feedback": "",
        "answer": "",
        "final_prompt": "",
        "stop_reason": "",
    }
```

`build_initial_state()` 先展开默认值，再覆盖输入字段。

目的：

- 所有单轮运行字段集中维护。
- 后续新增字段时更容易发现是否遗漏初始化。
- 避免 checkpoint 合并时继承上一轮业务状态。

## 修复 4：补测试

**文件：** `tests/test_langgraph_shadow.py`

新增或调整测试：

1. `test_resolve_thread_id_prefers_explicit_thread_id`
2. `test_resolve_thread_id_falls_back_to_session_id`
3. `test_run_langgraph_agent_uses_session_id_when_thread_id_missing`
4. `test_default_cached_graph_is_not_used_by_request_scoped_runs`
5. `test_build_initial_state_contains_run_state_defaults`

保留已有测试：

- `test_default_langgraph_agent_is_cached`
- `test_default_langgraph_agent_persists_checkpoints_by_thread_id`

但 checkpoint history 测试需要显式调用：

```python
run_langgraph_agent(..., use_cached_graph=True)
```

## 验证计划

运行：

```powershell
python -m unittest tests.test_langgraph_shadow -v
python -m unittest tests.test_recommendation_service -v
python -m unittest discover -v
python -m clothing_assistant.agent.eval_report
```

预期：

- request-scoped run 不污染 cached graph。
- 相同 `session_id` 在直接调用时得到稳定 `debug.thread_id`。
- 同一个 `thread_id/session_id` 下仍不会复用上一轮 `tool_results`、`stop_reason` 等单轮字段。
- 全量测试通过。

## 不做范围

- 不删除 `get_default_langgraph_agent()`。
- 不迁移 `AgentState` 到 Pydantic。
- 不改变 Java/Python streaming contract。
- 不改变 Java 对用户、商品、库存、价格、订单等事实的 source of truth 边界。

