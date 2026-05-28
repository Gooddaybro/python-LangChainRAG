# Python AI API Contract v1

契约版本：v1
发布日期：2026-05-28
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
- 返回 Java 商品库里的真实商品 ID。

v1 推荐结果只返回泛化推荐项，Java 后续可以在 v2 中把泛化推荐项映射到真实商品。

## 2. Endpoint

```text
POST /chat
Content-Type: application/json; charset=utf-8
```

Java 生产调用只接入 `/chat`。`/chat/pipeline` 和 `/chat/langgraph` 属于 Python 本地调试、迁移或兼容入口，不作为 Java 生产调用路径。

## 3. PythonChatRequest

```json
{
  "message": "我想买一件适合秋天通勤的外套",
  "thread_id": "th_20260528_abc123",
  "request_id": "req-uuid-001",
  "chat_history": [
    {
      "role": "user",
      "content": "上次你推荐的夹克是什么颜色的？"
    },
    {
      "role": "assistant",
      "content": "是深藏青色。"
    }
  ],
  "user_context": {
    "gender": "female",
    "height_cm": 165,
    "weight_kg": 55,
    "preferred_styles": ["commute", "casual"],
    "disliked_colors": ["yellow"],
    "budget_max_cny": 500
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `message` | string | 是 | 用户本次输入。不能为空字符串或纯空白字符串。 |
| `thread_id` | string | 是 | Java conversation-service 生成的会话线程标识。Python 只用于日志和追踪，不持久化会话。 |
| `request_id` | string | 是 | Java MDC/requestId，Python 原样回传，并写入日志。 |
| `chat_history` | array | 是 | Java 从 conversation-service 查询后组装。无历史时传 `[]`，不能传 `null`。 |
| `user_context` | object/null | 是 | Java 从 user-service 查询后组装。没有画像时传 `null`，Python 必须降级处理。 |

## 4. ChatHistoryItem

```json
{
  "role": "user",
  "content": "上次你推荐的夹克是什么颜色的？"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `role` | enum | 是 | 只能是 `user` 或 `assistant`。 |
| `content` | string | 是 | 历史消息正文。不能为空字符串或纯空白字符串。 |

规则：

- `chat_history` 最多 10 条消息，即最近 5 轮对话。
- 顺序必须从旧到新。
- 不包含本次 `message`，避免重复。
- Python 只读历史消息，不把它作为唯一事实来源。

## 5. UserContext

```json
{
  "gender": "female",
  "height_cm": 165,
  "weight_kg": 55,
  "preferred_styles": ["commute", "casual"],
  "disliked_colors": ["yellow"],
  "budget_max_cny": 500
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `gender` | string/null | 否 | 建议值：`male`、`female`、`unknown`。 |
| `height_cm` | number/null | 否 | 身高，单位 cm。 |
| `weight_kg` | number/null | 否 | 体重，单位 kg。 |
| `preferred_styles` | array | 否 | 偏好风格，例如 `commute`、`casual`、`sport`、`minimal`。 |
| `disliked_colors` | array | 否 | 用户不喜欢的颜色。 |
| `budget_max_cny` | number/null | 否 | 预算上限，单位人民币元。 |

规则：

- `user_context` 可以整体为 `null`。
- `user_context` 为对象时，内部字段都可缺省。
- 缺少画像时，Python 必须降级为风格建议或追问，不能因为画像缺失返回技术错误。
- 缺少身高体重时，Python 不应给出确定尺码结论。

## 6. PythonChatResponse

```json
{
  "reply": "这套搭配建议选择浅色短外套，整体会更清爽。",
  "recommendations": [
    {
      "type": "outerwear",
      "name": "浅色短款外套",
      "reason": "能提亮整体颜色，并和当前下装比例协调"
    }
  ],
  "intent": "recommendation",
  "request_id": "req-uuid-001"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `reply` | string | 是 | 用户可见的自然语言回复。 |
| `recommendations` | array | 是 | 泛化推荐项列表。无推荐时返回 `[]`，不能省略，不能返回 `null`。 |
| `intent` | enum | 是 | 本次对话意图，Java 可用于埋点和分析。 |
| `request_id` | string | 是 | 原样回传 Java 请求里的 `request_id`。 |

## 7. RecommendationItem

```json
{
  "type": "outerwear",
  "name": "浅色短款外套",
  "reason": "能提亮整体颜色，并和当前下装比例协调"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `type` | enum | 是 | 推荐品类，必须来自 v1 `type` 枚举表。 |
| `name` | string | 是 | AI 生成的泛化推荐名称，不是 Java 商品名。 |
| `reason` | string | 是 | 推荐理由，供 Java 保存和前端展示。 |

规则：

- v1 不返回 `product_id`、`spu_id`、`sku_id`。
- Python 不得编造 Java 商品 ID。
- 推荐项按推荐优先级从高到低排序。

## 8. `type` 枚举表

| 值 | 语义 |
| --- | --- |
| `outerwear` | 外套类，包含夹克、风衣、大衣。 |
| `top` | 上衣类，包含 T 恤、衬衫、毛衣。 |
| `bottom` | 下装类，包含裤子、半裙。 |
| `dress` | 连衣裙或套装。 |
| `shoes` | 鞋类。 |
| `bag` | 包类。 |
| `accessory` | 配件类，包含围巾、腰带、帽子。 |

Python 只能返回表内值。新增或重命名枚举值属于契约变更，必须更新版本。

## 9. `intent` 枚举表

| 值 | 语义 |
| --- | --- |
| `recommendation` | 推荐搭配或泛化商品。 |
| `size_advice` | 询问尺码或身材适配。 |
| `style_question` | 穿搭知识问答。 |
| `chitchat` | 闲聊，无具体购物意图。 |

Python 只能返回表内值。新增或重命名枚举值属于契约变更，必须更新版本。

## 10. 成功降级规则

以下情况返回 HTTP `200`，不视为技术错误：

- 没有用户画像：`user_context=null`，Python 给出泛化建议或追问。
- 无推荐结果：`recommendations=[]`，`reply` 解释原因。
- 缺少身高体重：Python 不给确定尺码，可改为追问。
- 用户闲聊：`intent=chitchat`，`recommendations=[]`。

示例：

```json
{
  "reply": "我还需要你的身高和体重大致范围，才能给出更可靠的尺码建议。",
  "recommendations": [],
  "intent": "size_advice",
  "request_id": "req-uuid-002"
}
```

## 11. 错误响应

技术错误响应统一使用：

```json
{
  "error": "validation_error",
  "message": "message must not be blank",
  "request_id": "req-uuid-001"
}
```

| HTTP 状态 | `error` | 场景 |
| --- | --- | --- |
| `422` | `validation_error` | 请求 JSON 结构不合法、必填字段缺失、字段类型错误、`message` 为空。 |
| `500` | `internal_server_error` | Python 服务内部未捕获异常。 |
| `503` | `ai_backend_unavailable` | LLM、向量库或关键 AI 后端不可用。 |

规则：

- 如果请求里能解析出 `request_id`，错误响应必须原样回传。
- 如果无法解析 `request_id`，错误响应里的 `request_id` 返回 `null`。
- 生产环境错误响应不能暴露 prompt、堆栈、密钥、内部路径或原始模型返回。
- 业务降级不要使用 `500` 或 `503`。

## 12. 版本规则

- v1 内允许增加可选字段，但 Java 侧不能依赖未声明字段。
- 删除字段、修改字段含义、修改必填性、修改枚举值，都属于破坏性变更，必须升级到 v2。
- Java 仓库的 `docs/contracts/CONTRACT_REF.md` 必须记录当前确认的契约版本和适配状态。
- 后续升级 OpenAPI 时，本 Markdown 契约应迁移为 `openapi.yaml`，并由 FastAPI 与 Java DTO 生成流程共同校验。
