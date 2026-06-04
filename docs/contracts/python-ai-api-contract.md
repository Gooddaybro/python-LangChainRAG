# Python AI API Contract v1

契约版本：v1
确认日期：2026-06-01
维护方：Python AI 服务仓库
调用方：Java 后端 assistant-service

本文档是 Java 后端调用 Python AI 导购服务的单一真相源。Java 仓库只保存引用和当前确认的契约版本，不复制本契约正文。

## 1. 范围

v1 只覆盖同步聊天接口：

```text
Java assistant-service
-> Python FastAPI POST /chat
-> PythonChatResponse
-> Java 保存会话消息和推荐结果
```

v1 不覆盖：

- `/chat/stream` 流式输出。
- MQ 异步 AI 任务。
- Python 主动调用 Java 商品 API。
- Python 持久化会话、订单、库存或交易事实。

## Streaming Contract Reference

`/chat/stream` 不在本文档内重复定义。流式接口以共享契约为准：

```text
..\outfit-project-contract\contracts\assistant-streaming-chat\v1.md
```

Python 项目只实现 Python -> Java 的 `token`、`done`、`error` 事件；Java -> 前端的 `meta`、`token`、`done`、`error` 转发由 Java 后端实现。

## 2. Endpoint

```text
POST /chat
Content-Type: application/json; charset=utf-8
```

Java 生产调用只接入 `/chat`。`/chat/pipeline` 和 `/chat/langgraph` 属于 Python 本地调试、迁移或兼容入口，不作为 Java 生产调用路径。

## 3. PythonChatRequest

```json
{
  "request_id": "req-uuid-001",
  "session_id": "th_20260601_abc123",
  "thread_id": "th_20260601_abc123",
  "query": "我想买一件适合秋天通勤的外套",
  "chat_history": [
    {
      "user_query": "上次你推荐的夹克是什么颜色的？",
      "assistant_answer": "是深藏青色。"
    }
  ],
  "user_context": {
    "user_id": 10001,
    "height_cm": 165,
    "weight_kg": 55,
    "gender": "female",
    "preferred_fit": "regular",
    "preferred_styles": ["commute", "casual"],
    "preferred_colors": ["black"],
    "disliked_colors": ["yellow"],
    "preferred_categories": ["外套"],
    "budget_min": null,
    "budget_max": 500
  },
  "candidates": [
    {
      "spu_id": 1002,
      "sku_id": 2004,
      "name": "通勤轻薄外套",
      "category": "外套",
      "sale_price": 299.0,
      "stock_status": "in_stock",
      "color": "黑色",
      "size": "L",
      "brand": null,
      "material": "聚酯纤维混纺",
      "fit_type": "regular",
      "season": ["autumn"],
      "style_tags": ["commute"],
      "main_image_url": "/images/products/jacket-commute-main.jpg"
    }
  ],
  "debug": false
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `request_id` | string | 是 | Java MDC/requestId，Python 原样回传，并写入日志。 |
| `session_id` | string | 是 | Java conversation-service 生成的会话标识。 |
| `thread_id` | string/null | 否 | LangGraph thread id；为空时 Python 使用 `session_id`。 |
| `query` | string | 是 | 用户本次输入。不能为空字符串或纯空白字符串。 |
| `chat_history` | array | 否 | Java 从 conversation-service 查询后组装。无历史时传 `[]` 或省略。 |
| `user_context` | object | 否 | Java 从 user-service 查询后组装。省略时 Python 使用空对象降级处理。 |
| `candidates` | array | 否 | Java 过滤后的候选商品池。无候选时传 `[]` 或省略。 |
| `debug` | boolean | 否 | 是否返回内部调试信息。生产默认 `false`。 |

## 4. ChatHistoryItem

```json
{
  "user_query": "我身高 165cm，体重 55kg，想买外套",
  "assistant_answer": "建议优先看 regular 版型。"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `user_query` | string | 否 | 上一轮用户问题。缺省时按空字符串处理。 |
| `assistant_answer` | string | 否 | 与上一轮用户问题配对的助手回答。缺省时按空字符串处理。 |

规则：

- `chat_history` 推荐最多 10 条问答对。
- 顺序必须从旧到新。
- 不包含本次 `query`，避免重复。
- Python 只读历史消息，不把它作为唯一事实来源。

## 5. UserContext

```json
{
  "user_id": 10001,
  "gender": "female",
  "height_cm": 165,
  "weight_kg": 55,
  "preferred_fit": "regular",
  "preferred_styles": ["commute", "casual"],
  "preferred_colors": ["black"],
  "disliked_colors": ["yellow"],
  "preferred_categories": ["外套"],
  "budget_min": null,
  "budget_max": 500
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `user_id` | number/string/null | 否 | Java 当前登录用户 id。 |
| `gender` | string/null | 否 | 建议值：`male`、`female`、`unknown`。 |
| `height_cm` | number/null | 否 | 身高，单位 cm。 |
| `weight_kg` | number/null | 否 | 体重，单位 kg。 |
| `preferred_fit` | string/null | 否 | 偏好版型，例如 `loose`、`regular`、`slim`。 |
| `preferred_styles` | array | 否 | 偏好风格，例如 `commute`、`casual`、`sport`、`minimal`。 |
| `preferred_colors` | array | 否 | 用户喜欢的颜色。 |
| `disliked_colors` | array | 否 | 用户不喜欢的颜色。 |
| `preferred_categories` | array | 否 | 用户偏好的商品品类。 |
| `budget_min` | number/null | 否 | 预算下限，单位人民币元。 |
| `budget_max` | number/null | 否 | 预算上限，单位人民币元。 |

规则：

- `user_context` 省略时，Python 必须降级为风格建议或追问，不能因为画像缺失返回技术错误。
- `user_context` 为对象时，内部字段都可缺省。
- 缺少身高体重时，Python 不应给出确定尺码结论。

## 6. ProductCandidate

```json
{
  "spu_id": 1002,
  "sku_id": 2004,
  "name": "通勤轻薄外套",
  "spu_code": "JACKET_COMMUTE_001",
  "sku_code": "JACKET_COMMUTE_001-BLACK-L",
  "category": "外套",
  "brand": null,
  "color": "黑色",
  "size": "L",
  "sale_price": 299.0,
  "stock_status": "in_stock",
  "available_stock": 8,
  "material": "聚酯纤维混纺",
  "fit_type": "regular",
  "season": ["autumn"],
  "style_tags": ["commute"],
  "main_image_url": "/images/products/jacket-commute-main.jpg"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `spu_id` | number/string | 是 | Java SPU id。 |
| `sku_id` | number/string | 是 | Java SKU id。 |
| `name` | string | 是 | 候选商品展示名。 |
| `spu_code` | string/null | 否 | Java SPU 编码。 |
| `sku_code` | string/null | 否 | Java SKU 编码。 |
| `category` | string/null | 否 | 商品品类。 |
| `brand` | string/null | 否 | 品牌。 |
| `color` | string/null | 否 | SKU 颜色。 |
| `size` | string/null | 否 | SKU 尺码。 |
| `sale_price` | number/null | 否 | 当前销售价，单位人民币元。 |
| `stock_status` | string/null | 否 | Java 库存状态，例如 `in_stock`、`low_stock`。 |
| `available_stock` | number/null | 否 | 可售库存。 |
| `material` | string/null | 否 | 材质。 |
| `fit_type` | string/null | 否 | 版型。 |
| `season` | array | 否 | 季节标签，例如 `autumn`。 |
| `style_tags` | array | 否 | 风格标签。 |
| `main_image_url` | string/null | 否 | 商品主图 URL。 |

## 7. PythonChatResponse

```json
{
  "request_id": "req-uuid-001",
  "answer": "推荐优先看通勤轻薄外套，版型选择 regular，更适合秋季叠穿。",
  "intent": "recommendation",
  "product_refs": [
    {
      "spu_id": 1002,
      "sku_id": 2004,
      "reason": "符合秋季通勤、regular 版型和预算条件",
      "rank_score": 0.95
    }
  ],
  "suggested_actions": [],
  "debug": null
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `request_id` | string | 是 | 原样回传 Java 请求里的 `request_id`。 |
| `answer` | string | 是 | 用户可见的自然语言回复。 |
| `intent` | string | 是 | 本次对话意图，Java 可用于埋点和分析。 |
| `product_refs` | array | 否 | Python 从 Java 候选池中选出的商品引用。无推荐时返回 `[]`。 |
| `suggested_actions` | array | 否 | 建议 Java 或前端执行的动作。无动作时返回 `[]`。 |
| `debug` | object/null | 否 | 仅在请求 `debug=true` 时返回内部调试信息。 |

## 8. ProductRef

```json
{
  "spu_id": 1002,
  "sku_id": 2004,
  "reason": "符合秋季通勤、regular 版型和预算条件",
  "rank_score": 0.95
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `spu_id` | number/string | 是 | Java SPU id。Python 不得编造候选池之外的 id。 |
| `sku_id` | number/string | 是 | Java SKU id。Python 不得编造候选池之外的 id。 |
| `reason` | string | 是 | 推荐理由，供 Java 保存和前端展示。 |
| `rank_score` | number/null | 否 | Python 排序分，值越大优先级越高。 |

规则：

- 推荐项必须来自请求里的 `candidates`。
- 推荐项按推荐优先级从高到低排序。

## 9. SuggestedAction

```json
{
  "type": "ask_follow_up",
  "spu_id": null,
  "sku_id": null
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `type` | string | 是 | 动作类型，例如 `ask_follow_up`。 |
| `spu_id` | number/string/null | 否 | 与动作关联的 SPU id。 |
| `sku_id` | number/string/null | 否 | 与动作关联的 SKU id。 |

## 10. `intent` 枚举表

| 值 | 语义 |
| --- | --- |
| `recommendation` | 推荐搭配或商品。 |
| `size_advice` | 询问尺码或身材适配。 |
| `product_qa` | 商品或库存问答。 |
| `style_question` | 穿搭知识问答。 |
| `chitchat` | 闲聊，无具体购物意图。 |
| `unknown` | Python 未能从 debug 中解析明确意图时的兜底值。 |

新增或重命名枚举值属于契约变更，必须更新版本。

## 11. 成功降级规则

以下情况返回 HTTP `200`，不视为技术错误：

- 没有用户画像：省略 `user_context` 或传空对象 `{}`，Python 给出泛化建议或追问。
- 无推荐结果：`product_refs=[]`，`answer` 解释原因。
- 缺少身高体重：Python 不给确定尺码，可改为追问。
- 用户闲聊：`intent=chitchat`，`product_refs=[]`。

示例：

```json
{
  "request_id": "req-uuid-002",
  "answer": "我还需要你的身高和体重大致范围，才能给出更可靠的尺码建议。",
  "intent": "size_advice",
  "product_refs": [],
  "suggested_actions": [
    {
      "type": "ask_follow_up",
      "spu_id": null,
      "sku_id": null
    }
  ]
}
```

## 12. 错误响应

请求校验错误由 FastAPI 统一返回：

```json
{
  "detail": [
    {
      "loc": ["body", "query"],
      "msg": "Field required",
      "type": "missing"
    }
  ],
  "body": {
    "request_id": "req-uuid-001"
  }
}
```

未捕获技术错误使用：

```json
{
  "error": "internal_server_error",
  "request_id": "req-uuid-001",
  "message": "AI service failed to process the request."
}
```

| HTTP 状态 | 场景 |
| --- | --- |
| `422` | 请求 JSON 结构不合法、必填字段缺失、字段类型错误、`query` 为空。 |
| `500` | Python 服务内部未捕获异常。 |

规则：

- 如果请求里能解析出 `request_id`，`500` 错误响应必须原样回传。
- 如果无法解析 `request_id`，`500` 错误响应里的 `request_id` 返回 `null`。
- 生产环境错误响应不能暴露 prompt、堆栈、密钥、内部路径或原始模型返回。
- 业务降级不要使用 `500`。

## 13. 版本规则

- v1 内允许增加可选字段，但 Java 侧不能依赖未声明字段。
- 删除字段、修改字段含义、修改必填性、修改枚举值，都属于破坏性变更，必须升级到 v2。
- Java 仓库的 `docs/contracts/CONTRACT_REF.md` 必须记录当前确认的契约版本和适配状态。
- 后续升级 OpenAPI 时，本 Markdown 契约应迁移为 `openapi.yaml`，并由 FastAPI 与 Java DTO 生成流程共同校验。
