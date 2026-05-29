# Java/Python 聊天接口调整开发文档

本文档说明如何把当前 Python FastAPI `/chat` 调整为 `java-python-chat-contract.md` 定义的 v0.1 同步契约。
本阶段只落地接口壳、请求字段透传、响应包装和测试，不实现候选商品排序、`ProductFactProvider`、Java internal API、SSE 或 MQ。

## 1. 开发目标

把生产入口 `/chat` 从当前旧格式：

```json
{
  "query": "你是谁？",
  "chat_history": [],
  "thread_id": "api-thread-1",
  "debug": false
}
```

调整为 Java 调用契约：

```json
{
  "request_id": "req-20260529-001",
  "session_id": "s-001",
  "thread_id": "s-001",
  "query": "你是谁？",
  "chat_history": [],
  "user_context": {},
  "candidates": [],
  "debug": false
}
```

生产 `/chat` 响应调整为：

```json
{
  "request_id": "req-20260529-001",
  "answer": "我是服装导购助手，可以帮你做尺码推荐、颜色搭配、洗涤养护和基础商品咨询。",
  "intent": "chat",
  "product_refs": [],
  "suggested_actions": []
}
```

当 `debug=true` 时，响应额外包含 `debug` 字段。

## 2. 本阶段边界

本阶段做：

- `/chat` 使用严格 Java 契约，请求必须带 `request_id` 和 `session_id`。
- `thread_id` 为空时使用 `session_id`。
- `request_id`、`session_id`、`user_context`、`candidates` 写入 LangGraph 初始 state。
- 响应包装为 `request_id/answer/intent/product_refs/suggested_actions/debug`。
- `missing_info` 自动映射为 `ask_follow_up` 建议动作。
- `/chat/pipeline` 和 `/chat/langgraph` 保持旧请求格式，作为本地兼容/调试入口。
- 500 错误响应收敛，不暴露内部异常字符串。
- 更新 API 单元测试。

本阶段不做：

- 不实现 `RequestCandidatesProvider`。
- 不升级 `product_catalog.json` 到 SPU/SKU。
- 不根据 `candidates` 生成真实 `product_refs`。
- 不接 Java internal API。
- 不改 SSE、MQ、鉴权、超时重试。
- 不重构 Streamlit 调试页。

## 3. 文件调整范围

### 3.1 新增 `clothing_assistant/api/schemas.py`

职责：

- 集中定义 API 请求/响应 Pydantic 模型。
- 避免 `app.py` 继续膨胀。

建议模型：

```text
ChatHistoryItem
UserContext
ProductCandidate
ProductRef
SuggestedAction
PythonChatRequest
PythonChatResponse
LegacyChatRequest
```

关键约束：

- `PythonChatRequest.request_id` 必填且不能空白。
- `PythonChatRequest.session_id` 必填且不能空白。
- `PythonChatRequest.query` 必填且不能空白。
- `LegacyChatRequest` 只用于 `/chat/pipeline` 和 `/chat/langgraph`。

### 3.2 修改 `clothing_assistant/api/app.py`

职责变化：

- 从 `schemas.py` 导入请求/响应模型。
- `/chat` 使用 `PythonChatRequest`。
- `/chat/pipeline` 和 `/chat/langgraph` 使用 `LegacyChatRequest`。
- 增加响应包装函数。
- 增加错误响应中的 `request_id` 提取逻辑。

注意当前工作区里 `app.py` 已有本地改动。实施时必须先读文件，保留用户已有改动，不做无关回滚。

### 3.3 修改 `clothing_assistant/agent/state.py`

新增可选状态字段：

```text
request_id
session_id
user_context
candidates
```

目的：

- 让 LangGraph debug/trace 能看到 Java 请求上下文。
- 后续接 `ProductFactProvider` 时不需要再改入口签名。

### 3.4 修改 `clothing_assistant/agent/langgraph_executor.py`

调整点：

- `run_langgraph_agent` 增加可选参数：

```text
request_id=None
session_id=None
user_context=None
candidates=None
```

- `build_initial_state` 接收并写入这些字段。
- `run_started` trace 记录 `request_id/session_id/thread_id/run_id`。

不改变：

- LangGraph 节点顺序。
- 现有路由逻辑。
- `InMemorySaver` 当前行为。

### 3.5 修改 `clothing_assistant/agent/agent_executor.py`

调整点：

- `build_response_from_state` 把 `request_id/session_id/user_context/candidates` 传给 `build_agent_response`。
- `build_agent_response` 的 debug 中增加：

```text
request_id
session_id
user_context
candidates
```

注意：

- 旧 pipeline `run_agent` 不需要强制带这些字段。
- 缺省值用 `None` 或空结构，避免破坏旧测试。

### 3.6 修改 `tests/test_api.py`

测试目标：

- `/chat` 新契约请求会调用 LangGraph。
- `/chat` 不带 `thread_id` 时使用 `session_id`。
- `/chat` `debug=false` 不返回 debug。
- `/chat` `debug=true` 返回 debug。
- `/chat` missing info 响应包含 `ask_follow_up`。
- `/chat` 缺少 `request_id` 返回 `422`。
- `/chat` 缺少 `session_id` 返回 `422`。
- `/chat/pipeline` 仍支持旧请求。
- `/chat/langgraph` 仍支持旧请求。

## 4. 实施任务

### Task 1: 定义 API Schema

**Files:**

- Create: `clothing_assistant/api/schemas.py`
- Test: `tests/test_api.py`

步骤：

1. 在 `tests/test_api.py` 增加 `/chat` 缺少 `request_id` 返回 `422` 的测试。
2. 在 `tests/test_api.py` 增加 `/chat` 缺少 `session_id` 返回 `422` 的测试。
3. 新建 `schemas.py`，定义 `PythonChatRequest`、`PythonChatResponse` 和兼容用 `LegacyChatRequest`。
4. 运行：

```powershell
python -m unittest tests.test_api -v
```

预期：

- 新测试开始应失败。
- 完成 schema 和 app 接入后应通过。

### Task 2: `/chat` 接入严格契约

**Files:**

- Modify: `clothing_assistant/api/app.py`
- Test: `tests/test_api.py`

步骤：

1. 把 `/chat` 请求模型从旧 `ChatRequest` 改为 `PythonChatRequest`。
2. 调用 `run_langgraph_agent` 时传入：

```text
query=request.query.strip()
chat_history=request.chat_history
thread_id=request.thread_id or request.session_id
request_id=request.request_id
session_id=request.session_id
user_context=request.user_context
candidates=request.candidates
```

3. `/chat/pipeline` 和 `/chat/langgraph` 使用 `LegacyChatRequest`，保持旧行为。
4. 更新 mock 断言。
5. 运行：

```powershell
python -m unittest tests.test_api -v
```

### Task 3: LangGraph State 透传 Java 上下文

**Files:**

- Modify: `clothing_assistant/agent/state.py`
- Modify: `clothing_assistant/agent/langgraph_executor.py`
- Modify: `clothing_assistant/agent/agent_executor.py`
- Test: `tests/test_langgraph_shadow.py`

步骤：

1. 在 `AgentState` 增加 `request_id/session_id/user_context/candidates`。
2. `run_langgraph_agent` 增加同名可选参数。
3. `build_initial_state` 写入这些字段。
4. `build_response_from_state` 和 `build_agent_response` 在 debug 中返回这些字段。
5. 增加 LangGraph 测试，断言：

```text
debug.request_id == 请求 request_id
debug.session_id == 请求 session_id
debug.user_context == 请求 user_context
debug.candidates == 请求 candidates
```

6. 运行：

```powershell
python -m unittest tests.test_langgraph_shadow -v
```

### Task 4: 契约响应包装

**Files:**

- Modify: `clothing_assistant/api/app.py`
- Test: `tests/test_api.py`

步骤：

1. 替换当前 `build_chat_response(agent_result, include_debug)`。
2. 新包装函数输出：

```text
request_id
answer
intent
product_refs
suggested_actions
debug only when include_debug=true
```

3. `intent` 读取：

```text
agent_result["debug"]["intent_result"]["intent"]
```

如果缺失，使用 `unknown`。

4. `product_refs` 第一阶段固定为空数组。
5. `suggested_actions` 映射规则：

```text
debug.stop_reason == "missing_info" -> [{"type": "ask_follow_up"}]
其他 -> []
```

6. 运行：

```powershell
python -m unittest tests.test_api -v
```

### Task 5: 错误响应收敛

**Files:**

- Modify: `clothing_assistant/api/app.py`
- Test: `tests/test_api.py`

步骤：

1. 修改全局异常处理器，不再返回 `detail=str(exc)`。
2. 尝试从请求 JSON 中读取 `request_id`。
3. 返回：

```json
{
  "error": "internal_server_error",
  "request_id": "req-xxx",
  "message": "AI service failed to process the request."
}
```

4. 增加测试：mock `run_langgraph_agent` 抛异常，断言 500 响应不包含内部异常文本。
5. 运行：

```powershell
python -m unittest tests.test_api -v
```

### Task 6: 全量验证

**Files:**

- No new files.

步骤：

1. 运行 API 测试：

```powershell
python -m unittest tests.test_api -v
```

2. 运行 LangGraph 相关测试：

```powershell
python -m unittest tests.test_langgraph_shadow tests.test_langgraph_production_nodes -v
```

3. 运行编译检查：

```powershell
python -m compileall -q clothing_assistant tests
```

4. 如果只改接口层但全量测试时间可接受，运行：

```powershell
python -m unittest discover -v
```

## 5. 验收标准

完成后应满足：

- `/chat` 必须使用 `request_id/session_id/query`。
- `/chat` 响应总是包含 `request_id/answer/intent/product_refs/suggested_actions`。
- `debug=false` 不返回 debug。
- `debug=true` 返回 debug。
- `thread_id` 未传时使用 `session_id`。
- Java 上下文可在 LangGraph debug 中看到。
- 缺信息响应带 `ask_follow_up`。
- 500 响应不暴露内部异常字符串。
- `/chat/pipeline` 和 `/chat/langgraph` 仍支持旧请求结构。

## 6. 后续阶段

本阶段通过后，再进入下一阶段：

1. `RequestCandidatesProvider`。
2. JSON 商品模型升级到 SPU/SKU。
3. 基于 `candidates` 生成 `product_refs` 和推荐理由。
4. Java internal API provider。
5. 鉴权、超时、requestId 与 Java MDC 联动。
