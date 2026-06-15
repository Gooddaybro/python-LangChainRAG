# LangGraph 路由与答案校验开发计划

> **给后续执行者：** 按任务逐项执行，使用测试先行。每个任务都用 `- [ ]` 复选框跟踪进度。

**目标：** 让当前 LangGraph 在图结构层面真实体现检索质量分流和答案校验重试，同时保持现有 Java/Python 职责边界和外部响应契约不变。

**架构：** 现在的弱检索兜底和答案校验失败处理主要藏在节点内部。优化后，`retrieval_grader` 负责产出显式路由判断，弱检索或空检索进入独立的 `fallback_answer` 节点；`answer_validator` 负责判断答案是否通过、是否可重试，图上的条件边决定继续生成、落兜底，还是进入日志节点。`direct_answer_gate` 的职责拆分先作为后续清理项。

**技术栈：** Python、LangGraph `StateGraph`、`TypedDict` 状态、Python `unittest`、现有 `ToolRegistry`、共享合同 `D:\git\outfit-project-contract\contracts\assistant-streaming-chat\v1.md`。

---

## 文件范围

- 修改 `clothing_assistant/agent/state.py`：增加检索路由、生成次数、校验反馈和兜底结果字段。
- 修改 `clothing_assistant/agent/nodes.py`：增加路由函数、兜底节点、重试感知的生成逻辑和更明确的 validator 输出。
- 修改 `clothing_assistant/agent/langgraph_executor.py`：把线性的 grader/validator 边改成条件边。
- 修改 `clothing_assistant/application/answer_service.py`：把新增调试字段暴露到 `debug`，不改变顶层响应结构。
- 修改 `tests/test_langgraph_production_nodes.py`：覆盖 good、weak、empty 三类检索路由。
- 修改 `tests/test_langgraph_shadow.py`：覆盖 validator 有界重试和重试耗尽兜底。
- 修改 `docs/langgraph-flow.md`：实现完成后同步更新图文档。

## 边界

本计划只调整 Python LangGraph 编排。

不做这些事：

- 不修改 Java 后端。
- 不修改前端。
- 不修改共享 streaming contract 版本。
- 不改变 `/chat`、`/chat/stream` 或 SSE 事件字段含义。
- 不让 Python 编造商品、价格、库存、订单、支付或用户归属事实。
- 不返回无法追溯到 Java 提供候选商品的 `product_refs`。

政策类问题继续走现有 `policy_tool` 和 `policy_fallback` 路径。普通 RAG 弱证据不应该走 `policy_fallback`，因为 `policy_fallback` 只负责政策意图和政策来源兜底。

## 目标图结构

```text
rag_retriever
-> retrieval_grader
   -> good  -> answer_generator
   -> weak  -> fallback_answer
   -> empty -> fallback_answer

answer_generator
-> answer_validator
   -> pass          -> trace_logger
   -> retry         -> answer_generator
   -> final_failure -> fallback_answer

fallback_answer
-> trace_logger
```

`direct_answer_gate` 第一阶段保持不变。后续可以拆成：

```text
direct_answer_gate
-> direct_answer_generator
-> trace_logger
```

## 状态契约

给 `AgentState` 增加这些可选字段：

```python
retrieval_route: dict[str, Any]
generation_attempts: int
max_generation_attempts: int
validation_feedback: str
fallback_result: dict[str, Any]
```

典型值：

```python
retrieval_route = {
    "status": "good",  # "good" | "weak" | "empty" | "skipped"
    "reason": "accepted_chunks_available",
    "accepted_count": 1,
    "rejected_count": 0,
}

validation_result = {
    "grounded": False,
    "retryable": True,
    "reason": "empty_draft_answer",
}

fallback_result = {
    "kind": "retrieval_fallback",
    "reason": "no accepted retrieval evidence",
}
```

## 任务 1：补检索路由失败测试

**文件：**
- 修改：`tests/test_langgraph_production_nodes.py`

- [ ] **步骤 1：增加空检索 fake**

在现有 fake RAG runner 附近增加：

```python
def empty_rag_runner(query, query_type=None):
    return {
        "retrieval_query": query,
        "retrieved_chunks": [],
        "source_count": 0,
    }
```

- [ ] **步骤 2：增强弱检索测试**

更新 `test_weak_retrieval_is_rejected_before_final_answer`，要求弱检索绕过 `answer_generator`：

```python
def test_weak_retrieval_is_rejected_before_final_answer(self):
    result = run_langgraph_agent(
        "日常通勤推荐什么颜色？",
        tool_registry=build_registry(rag_runner=weak_rag_runner),
        answer_generator=fake_answer_generator,
    )
    debug = result["debug"]
    trace_steps = [event["step"] for event in debug["trace_events"]]

    self.assertEqual(debug["selected_tools"], ["rag_tool"])
    self.assertEqual(debug["accepted_chunks"], [])
    self.assertEqual(debug["retrieval_route"]["status"], "weak")
    self.assertEqual(debug["stop_reason"], "answer_fallback")
    self.assertIn("没有检索到足够可靠", result["answer"])
    self.assertIn("retrieval_grader", trace_steps)
    self.assertIn("fallback_answer", trace_steps)
    self.assertNotIn("answer_generated", trace_steps)
```

- [ ] **步骤 3：增加空检索路由测试**

新增：

```python
def test_empty_retrieval_routes_to_fallback_answer(self):
    result = run_langgraph_agent(
        "日常通勤推荐什么颜色？",
        tool_registry=build_registry(rag_runner=empty_rag_runner),
        answer_generator=fake_answer_generator,
    )
    debug = result["debug"]
    trace_steps = [event["step"] for event in debug["trace_events"]]

    self.assertEqual(debug["selected_tools"], ["rag_tool"])
    self.assertEqual(debug["accepted_chunks"], [])
    self.assertEqual(debug["rejected_chunks"], [])
    self.assertEqual(debug["retrieval_route"]["status"], "empty")
    self.assertEqual(debug["stop_reason"], "answer_fallback")
    self.assertIn("fallback_answer", trace_steps)
    self.assertNotIn("answer_generated", trace_steps)
```

- [ ] **步骤 4：运行测试确认失败**

```powershell
python -m unittest tests.test_langgraph_production_nodes.LangGraphProductionNodeTests -v
```

预期：失败原因是 `retrieval_route`、`fallback_answer` 还不存在，弱检索仍经过了 `answer_generator`。

## 任务 2：实现检索路由和兜底节点

**文件：**
- 修改：`clothing_assistant/agent/state.py`
- 修改：`clothing_assistant/agent/nodes.py`
- 修改：`clothing_assistant/agent/langgraph_executor.py`
- 修改：`clothing_assistant/application/answer_service.py`

- [ ] **步骤 1：扩展 `AgentState`**

在中间结果字段附近加入：

```python
retrieval_route: dict[str, Any]
generation_attempts: int
max_generation_attempts: int
validation_feedback: str
fallback_result: dict[str, Any]
```

- [ ] **步骤 2：初始化生成重试状态**

在 `build_initial_state` 中加入：

```python
"generation_attempts": 0,
"max_generation_attempts": 2,
"validation_feedback": "",
```

- [ ] **步骤 3：让 `retrieval_grader_node` 产出路由状态**

无 RAG 结果时：

```python
retrieval_route = {
    "status": "skipped",
    "reason": "rag_result_missing",
    "accepted_count": 0,
    "rejected_count": 0,
}
```

有 RAG 结果时：

```python
if accepted_chunks:
    status = "good"
    reason = "accepted_chunks_available"
elif chunks:
    status = "weak"
    reason = "all_retrieved_chunks_rejected"
else:
    status = "empty"
    reason = "retrieved_chunks_empty"
```

- [ ] **步骤 4：增加 `route_after_retrieval_grader`**

```python
def route_after_retrieval_grader(state):
    status = (state.get("retrieval_route") or {}).get("status")

    if status == "good":
        return "answer_generator"

    if status in {"weak", "empty"}:
        return "fallback_answer"

    return "answer_generator"
```

- [ ] **步骤 5：增加 `fallback_answer_node`**

该节点负责两类兜底：

- `retrieval_fallback`：弱检索或空检索。
- `validation_fallback`：答案校验失败且重试次数耗尽。

弱检索兜底仍要写入：

```python
validation_result = {
    "grounded": False,
    "retryable": False,
    "reason": "no accepted retrieval evidence",
}
```

这样可以保留现有 debug 语义。

- [ ] **步骤 6：把 `retrieval_grader` 改为条件边**

```python
graph.add_conditional_edges(
    "retrieval_grader",
    route_after_retrieval_grader,
    {
        "answer_generator": "answer_generator",
        "fallback_answer": "fallback_answer",
    },
)
graph.add_edge("fallback_answer", "trace_logger")
```

- [ ] **步骤 7：把新字段暴露到 debug**

新增 debug 字段：

```python
"retrieval_route": retrieval_route or {},
"generation_attempts": generation_attempts,
"validation_feedback": validation_feedback or "",
"fallback_result": fallback_result or {},
```

- [ ] **步骤 8：运行聚焦测试**

```powershell
python -m unittest tests.test_langgraph_production_nodes.LangGraphProductionNodeTests -v
```

预期：`LangGraphProductionNodeTests` 全部通过。

## 任务 3：补 validator 重试失败测试

**文件：**
- 修改：`tests/test_langgraph_shadow.py`

- [ ] **步骤 1：增加先空后成功的生成器**

```python
def empty_then_valid_answer_generator(state):
    if state.get("generation_attempts", 0) == 0:
        return "", "empty first draft"

    return "根据资料，日常通勤可以优先选择低饱和颜色。", "retry prompt"
```

- [ ] **步骤 2：增加重试后通过测试**

```python
def test_answer_validator_retries_once_for_empty_draft(self):
    result = run_langgraph_agent(
        "日常通勤推荐什么颜色？",
        tool_registry=build_fake_registry(),
        answer_generator=empty_then_valid_answer_generator,
    )
    debug = result["debug"]
    trace_steps = [event["step"] for event in debug["trace_events"]]

    self.assertEqual(debug["stop_reason"], "final_answer")
    self.assertEqual(debug["generation_attempts"], 2)
    self.assertEqual(debug["validation_result"]["grounded"], True)
    self.assertIn("日常通勤", result["answer"])
    self.assertGreaterEqual(trace_steps.count("answer_generated"), 2)
    self.assertGreaterEqual(trace_steps.count("answer_validated"), 2)
```

- [ ] **步骤 3：增加一直空的生成器**

```python
def always_empty_answer_generator(state):
    return "", "always empty draft"
```

- [ ] **步骤 4：增加重试耗尽兜底测试**

```python
def test_answer_validator_falls_back_after_retry_limit(self):
    result = run_langgraph_agent(
        "日常通勤推荐什么颜色？",
        tool_registry=build_fake_registry(),
        answer_generator=always_empty_answer_generator,
    )
    debug = result["debug"]
    trace_steps = [event["step"] for event in debug["trace_events"]]

    self.assertEqual(debug["stop_reason"], "answer_fallback")
    self.assertEqual(debug["generation_attempts"], 2)
    self.assertEqual(debug["validation_result"]["grounded"], False)
    self.assertEqual(debug["validation_result"]["reason"], "empty_draft_answer")
    self.assertIn("fallback_answer", trace_steps)
```

- [ ] **步骤 5：运行测试确认失败**

```powershell
python -m unittest tests.test_langgraph_shadow.LangGraphShadowTests -v
```

预期：失败原因是生成次数、validator 重试路由、重试耗尽兜底还没有实现。

## 任务 4：实现 validator 有界重试

**文件：**
- 修改：`clothing_assistant/agent/nodes.py`
- 修改：`clothing_assistant/agent/langgraph_executor.py`

- [ ] **步骤 1：在 `answer_generator_node` 计数**

每次进入生成节点时：

```python
generation_attempts = state.get("generation_attempts", 0) + 1
```

注入的 `answer_generator` 看到的是“进入本次生成前已经尝试了几次”：

```python
generator_state = dict(state)
generator_state["generation_attempts"] = generation_attempts - 1
generator_state["validation_feedback"] = state.get("validation_feedback", "")
```

- [ ] **步骤 2：让 validator 对空草稿返回可重试失败**

```python
validation_result = {
    "grounded": False,
    "retryable": True,
    "reason": "empty_draft_answer",
}
```

并写入：

```python
"validation_feedback": "上一版回答为空，请基于已接受证据生成保守回答。"
```

- [ ] **步骤 3：增加 `route_after_answer_validator`**

```python
def route_after_answer_validator(state):
    validation_result = state.get("validation_result") or {}

    if validation_result.get("grounded"):
        return "trace_logger"

    if validation_result.get("retryable") and state.get("generation_attempts", 0) < state.get("max_generation_attempts", 2):
        return "answer_generator"

    return "fallback_answer"
```

- [ ] **步骤 4：把 validator 改成条件边**

```python
graph.add_conditional_edges(
    "answer_validator",
    route_after_answer_validator,
    {
        "trace_logger": "trace_logger",
        "answer_generator": "answer_generator",
        "fallback_answer": "fallback_answer",
    },
)
```

- [ ] **步骤 5：运行 validator 测试**

```powershell
python -m unittest tests.test_langgraph_shadow.LangGraphShadowTests -v
```

预期：新增 validator 重试测试和旧测试都通过。

## 任务 5：更新 LangGraph 文档

**文件：**
- 修改：`docs/langgraph-flow.md`

- [ ] **步骤 1：更新图结构**

文档应描述：

```text
retrieval_grader
├── good -> answer_generator
├── weak -> fallback_answer
└── empty -> fallback_answer

answer_validator
├── pass -> trace_logger
├── retry -> answer_generator
└── final_failure -> fallback_answer
```

- [ ] **步骤 2：补状态字段说明**

补充：

```text
retrieval_route
generation_attempts
max_generation_attempts
validation_feedback
fallback_result
```

- [ ] **步骤 3：说明弱 RAG 不走 policy fallback**

```text
普通 RAG 弱证据或空证据进入 fallback_answer，不进入 policy_fallback。
policy_fallback 仅用于 policy intent 与 policy_tool 来源处理。
```

- [ ] **步骤 4：搜索一致性**

```powershell
rg -n "retrieval_grader|answer_validator|fallback_answer|answer_fallback|policy_fallback" docs clothing_assistant tests -S
```

预期：文档不再声称 `retrieval_grader` 总是直接进入 `answer_generator`。

## 任务 6：完整验证

- [ ] **步骤 1：运行 LangGraph 聚焦测试**

```powershell
python -m unittest tests.test_langgraph_production_nodes tests.test_langgraph_shadow -v
```

- [ ] **步骤 2：运行完整测试**

```powershell
python -m unittest discover -v
```

- [ ] **步骤 3：运行 eval report**

```powershell
python -m clothing_assistant.agent.eval_report
```

## 验收标准

- weak/empty RAG 不再进入 `answer_generator` 图节点。
- `retrieval_route` 出现在 `debug`。
- 生成答案不合格时，`answer_validator` 可以带着 `validation_feedback` 触发重试。
- 重试次数受 `max_generation_attempts` 限制。
- 重试耗尽进入 `fallback_answer`。
- 商品、价格、库存、订单、支付、用户身份和持久化边界不变。
- `/chat` 和 `/chat/stream` 合同保持兼容。
- 现有弱检索仍返回保守兜底答案。

## 延后清理

`direct_answer_gate` 当前同时判断和生成直接答案，但只处理低风险短路场景，例如自我介绍和 unknown intent。等检索分流与 validator 重试稳定后，再拆成：

```text
direct_answer_gate -> direct_answer_generator -> trace_logger
direct_answer_gate -> missing_info_gate
```

拆分时需要补一个聚焦测试：直接回答仍不调用工具，并保持 `stop_reason = "direct_answer"`。
