# Java/Python 聊天接口 Reqable 调试文档

本文档用于接口调整完成后的本地调试和 Java/Python 联调。
当前文档按 `java-python-chat-contract.md` 的 v0.1 契约编写，主调试工具使用 Reqable。

## 1. 启动 Python FastAPI

在 Python 项目根目录运行：

```powershell
uvicorn clothing_assistant.api.app:app --reload
```

默认地址：

```text
http://127.0.0.1:8000
```

如果端口被占用：

```powershell
uvicorn clothing_assistant.api.app:app --reload --port 8001
```

Swagger 只作为接口结构查看入口，不作为本文档的主调试方式：

```text
http://127.0.0.1:8000/docs
```

## 2. Reqable 环境配置

在 Reqable 中创建环境：

```text
Environment name: local-python
```

环境变量：

```text
base_url = http://127.0.0.1:8000
```

如果 Python 服务使用 `8001` 端口：

```text
base_url = http://127.0.0.1:8001
```

建议创建一个集合：

```text
Collection: AI Clothing Assistant - Python API
```

后续请求都保存到这个集合，便于 Java/Python 联调时反复发送和对比响应。

## 3. Reqable 公共 Header

所有 POST 请求统一设置：

```text
Content-Type: application/json; charset=utf-8
```

如果后续接入内部鉴权，再追加：

```text
Authorization: Bearer <internal-token>
```

当前 v0.1 接口调整阶段不要求鉴权。

## 4. 健康检查

Reqable 请求配置：

```text
Name: health
Method: GET
URL: {{base_url}}/health
```

预期：

```json
{
  "status": "ok"
}
```

检查点：

- HTTP 状态码为 `200`。
- 如果请求失败，先确认 Python FastAPI 是否已经启动。

## 5. 最小 `/chat` 请求

Reqable 请求配置：

```text
Name: chat - minimal
Method: POST
URL: {{base_url}}/chat
Header: Content-Type: application/json; charset=utf-8
Body type: JSON
```

Body:

```json
{
  "request_id": "req-local-001",
  "session_id": "s-local-001",
  "query": "你是谁？",
  "chat_history": [],
  "user_context": {},
  "candidates": [],
  "debug": false
}
```

预期响应结构：

```json
{
  "request_id": "req-local-001",
  "answer": "我是服装导购助手，可以帮你做尺码推荐、颜色搭配、洗涤养护和基础商品咨询。",
  "intent": "chat",
  "product_refs": [],
  "suggested_actions": []
}
```

检查点：

- HTTP 状态码为 `200`。
- `request_id` 必须和请求一致。
- `intent` 应为 `chat`。
- `debug=false` 时不应返回 `debug`。
- `product_refs` 第一阶段为空数组是预期行为。

## 6. Debug 模式请求

Reqable 请求配置：

```text
Name: chat - debug
Method: POST
URL: {{base_url}}/chat
Header: Content-Type: application/json; charset=utf-8
Body type: JSON
```

Body:

```json
{
  "request_id": "req-local-debug-001",
  "session_id": "s-local-debug-001",
  "query": "你是谁？",
  "chat_history": [],
  "user_context": {
    "user_id": 10001,
    "height_cm": 175,
    "weight_kg": 70,
    "preferred_fit": "regular",
    "preferred_styles": ["commute"]
  },
  "candidates": [],
  "debug": true
}
```

预期 debug 中能看到：

```text
debug.request_id
debug.session_id
debug.thread_id
debug.intent_result
debug.selected_tools
debug.stop_reason
debug.trace_events
debug.user_context
debug.candidates
```

检查点：

- `debug.request_id` 应等于请求里的 `request_id`。
- `debug.session_id` 应等于请求里的 `session_id`。
- 未传 `thread_id` 时，`debug.thread_id` 应等于 `session_id`。
- `debug.user_context` 应保留 Java 传入的用户画像。

## 7. 缺信息调试

Reqable 请求配置：

```text
Name: chat - missing info
Method: POST
URL: {{base_url}}/chat
Header: Content-Type: application/json; charset=utf-8
Body type: JSON
```

Body:

```json
{
  "request_id": "req-local-missing-001",
  "session_id": "s-local-missing-001",
  "query": "黑色M码有货吗？",
  "chat_history": [],
  "user_context": {},
  "candidates": [],
  "debug": true
}
```

预期响应包含：

```json
{
  "request_id": "req-local-missing-001",
  "intent": "inventory_check",
  "product_refs": [],
  "suggested_actions": [
    {
      "type": "ask_follow_up"
    }
  ]
}
```

检查点：

- HTTP 状态码为 `200`。
- `answer` 应追问用户补充商品名或 SKU。
- `debug.stop_reason` 应为 `missing_info`。
- `debug.missing_info_result.missing_fields` 应包含 `product`。
- `suggested_actions[0].type` 应为 `ask_follow_up`。

## 8. 候选商品请求样例

第一阶段 Python 还不会基于 `candidates` 生成真实 `product_refs`，但接口应能接收并在 debug 中透传。

Reqable 请求配置：

```text
Name: chat - candidates passthrough
Method: POST
URL: {{base_url}}/chat
Header: Content-Type: application/json; charset=utf-8
Body type: JSON
```

Body:

```json
{
  "request_id": "req-local-candidates-001",
  "session_id": "s-local-candidates-001",
  "query": "我 175cm 70kg，想买一件适合通勤的外套",
  "chat_history": [],
  "user_context": {
    "user_id": 10001,
    "height_cm": 175,
    "weight_kg": 70,
    "preferred_fit": "regular",
    "preferred_styles": ["commute"],
    "preferred_colors": ["black", "navy"],
    "budget_min": 100,
    "budget_max": 400
  },
  "candidates": [
    {
      "spu_id": 1001,
      "spu_code": "SPU-JK-001",
      "sku_id": 2001,
      "sku_code": "SKU-JK-001-BLACK-L",
      "name": "通勤轻薄外套",
      "category": "外套",
      "brand": "DemoBrand",
      "color": "黑色",
      "size": "L",
      "sale_price": 299,
      "stock_status": "in_stock",
      "available_stock": 7,
      "material": "聚酯纤维混纺",
      "fit_type": "regular",
      "season": ["spring", "autumn"],
      "style_tags": ["commute", "minimal"],
      "main_image_url": "https://example.com/image.jpg"
    }
  ],
  "debug": true
}
```

本阶段预期：

- HTTP 状态码为 `200`。
- 响应符合契约字段。
- `debug.candidates[0].spu_id` 等于 `1001`。
- `product_refs` 仍可能为空数组。

## 9. 参数校验调试

### 9.1 缺少 `request_id`

Reqable 请求配置：

```text
Name: chat - invalid missing request_id
Method: POST
URL: {{base_url}}/chat
Header: Content-Type: application/json; charset=utf-8
Body type: JSON
```

Body:

```json
{
  "session_id": "s-local-invalid-001",
  "query": "你是谁？"
}
```

预期：

```text
HTTP 422
```

### 9.2 缺少 `session_id`

Reqable 请求配置：

```text
Name: chat - invalid missing session_id
Method: POST
URL: {{base_url}}/chat
Header: Content-Type: application/json; charset=utf-8
Body type: JSON
```

Body:

```json
{
  "request_id": "req-local-invalid-002",
  "query": "你是谁？"
}
```

预期：

```text
HTTP 422
```

### 9.3 空 `query`

Reqable 请求配置：

```text
Name: chat - invalid blank query
Method: POST
URL: {{base_url}}/chat
Header: Content-Type: application/json; charset=utf-8
Body type: JSON
```

Body:

```json
{
  "request_id": "req-local-invalid-003",
  "session_id": "s-local-invalid-003",
  "query": "   "
}
```

预期：

```text
HTTP 422
```

检查点：

- Reqable 响应面板中状态码应为 `422`。
- 这属于参数校验失败，不应进入 LangGraph。

## 10. 兼容入口调试

这两个入口只用于 Python 本地调试和迁移对照，不作为 Java 生产调用路径。

### 10.1 `/chat/langgraph`

Reqable 请求配置：

```text
Name: compat - chat langgraph
Method: POST
URL: {{base_url}}/chat/langgraph
Header: Content-Type: application/json; charset=utf-8
Body type: JSON
```

Body:

```json
{
  "query": "你是谁？",
  "chat_history": [],
  "debug": true
}
```

### 10.2 `/chat/pipeline`

Reqable 请求配置：

```text
Name: compat - chat pipeline
Method: POST
URL: {{base_url}}/chat/pipeline
Header: Content-Type: application/json; charset=utf-8
Body type: JSON
```

Body:

```json
{
  "query": "你是谁？",
  "chat_history": [],
  "debug": true
}
```

预期：

- 两个兼容入口继续支持旧请求结构。
- Java 生产调用不要使用这两个入口。

## 11. Reqable 调试建议

建议保存这些请求模板：

```text
health
chat - minimal
chat - debug
chat - missing info
chat - candidates passthrough
chat - invalid missing request_id
chat - invalid missing session_id
chat - invalid blank query
compat - chat langgraph
compat - chat pipeline
```

建议每次联调时观察：

- HTTP 状态码。
- 响应耗时。
- `request_id` 是否原样返回。
- `intent` 是否符合预期。
- `debug.stop_reason` 是否符合预期。
- `product_refs` 是否只包含允许的数据。
- `suggested_actions` 是否能驱动前端或 Java 后续流程。

## 12. 单元测试命令

接口改造后优先运行：

```powershell
python -m unittest tests.test_api -v
```

LangGraph 透传字段相关测试：

```powershell
python -m unittest tests.test_langgraph_shadow -v
```

生产节点回归：

```powershell
python -m unittest tests.test_langgraph_production_nodes -v
```

编译检查：

```powershell
python -m compileall -q clothing_assistant tests
```

可选全量回归：

```powershell
python -m unittest discover -v
```

## 13. 常见问题排查

### 13.1 Reqable 连接失败

检查：

- FastAPI 是否已经启动。
- `base_url` 是否是 `http://127.0.0.1:8000` 或实际端口。
- Windows 防火墙或代理是否拦截本地请求。

### 13.2 `/chat` 返回 422

检查：

- 是否传了 `request_id`。
- 是否传了 `session_id`。
- `query` 是否为空字符串或纯空白。
- Header 是否包含 `Content-Type: application/json; charset=utf-8`。
- Reqable Body 类型是否选择 JSON。

### 13.3 `thread_id` 不是预期值

规则：

```text
如果请求传 thread_id，则使用 thread_id。
如果请求不传 thread_id，则使用 session_id。
```

检查：

- `debug.thread_id`
- `debug.trace_events[0].data.thread_id`

### 13.4 Java 看不到 debug

检查请求：

```json
{
  "debug": true
}
```

生产默认应使用 `debug=false`，避免暴露内部 trace。

### 13.5 响应没有商品引用

本阶段这是预期行为。

原因：

- 这次只改接口契约和字段透传。
- `RequestCandidatesProvider` 和候选排序不在本阶段。
- `product_refs` 会在下一阶段基于 `candidates` 生成。

### 13.6 500 响应没有异常详情

这是预期行为。

生产契约要求不暴露内部异常字符串。排查应看 Python 服务日志，而不是把异常详情返回给 Java 或前端。

## 14. Java 联调检查清单

Java `assistant-service` 调 Python 前确认：

- 已生成 `request_id`。
- 已生成或读取 `session_id`。
- 已把历史消息组装为 `chat_history`。
- 已把用户画像组装为 `user_context`。
- 第一阶段可以传空 `candidates`，但生产推荐质量会受限。
- HTTP 超时由 Java 调用侧控制。

Java 收到响应后确认：

- `response.request_id == request.request_id`。
- `answer` 保存到 assistant message。
- `intent` 保存到 assistant message 或推荐记录。
- `product_refs` 为空时不创建推荐商品明细。
- `suggested_actions` 包含 `ask_follow_up` 时，前端展示追问即可，不进入加购流程。
