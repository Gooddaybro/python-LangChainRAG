# Java 与 Python 聊天契约 v0.1

本文档定义 Java 后端调用 Python AI 导购服务的第一版 HTTP 契约。
目标是先锁定 `assistant-service` 与 FastAPI `/chat` 之间的字段边界，让 Java 和 Python 可以独立开发、独立测试，再通过同一份契约联调。

## 1. 范围

本契约主要覆盖第一阶段同步聊天：

```text
Java assistant-service
-> Python FastAPI POST /chat
-> LangGraph Agent
-> PythonChatResponse
-> Java 保存消息和推荐结果
```

第一阶段不覆盖：

- MQ 异步 AI 任务。
- Python 主动调用 Java internal product API。
- Python 持久化会话或订单状态。

`/chat/stream` 已在 2026-06-19 纳入轻量回归测试，测试范围见本文末尾“流式接口回归边界”。

第一阶段边界：

- Java 负责用户、商品、SKU、价格、库存、购物车、订单、会话和推荐结果沉淀。
- Python 负责意图识别、缺信息追问、RAG 知识问答、候选商品排序解释和导购回答生成。
- Python 不创建订单、不修改库存、不保存交易事实。
- Python 对商品候选只读，最终购买动作仍回到 Java 校验。

## 2. Endpoint

```text
POST /chat
Content-Type: application/json; charset=utf-8
```

Java 只接入 `/chat`。`/chat/pipeline` 和 `/chat/langgraph` 属于 Python 本地迁移、调试或兼容入口，不作为 Java 生产调用路径。

## 3. PythonChatRequest

```json
{
  "request_id": "req-20260528-001",
  "session_id": "s-001",
  "thread_id": "s-001",
  "query": "我 175cm 70kg，想买一件适合通勤的外套",
  "chat_history": [],
  "user_context": {},
  "candidates": [],
  "debug": false
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `request_id` | string | 是 | Java 生成的链路 id。Python 原样返回，并写入 debug/trace。 |
| `session_id` | string | 是 | Java 会话 id，用于 Java 保存消息和推荐结果。 |
| `thread_id` | string | 否 | LangGraph 本轮运行标识。为空时 Python 可使用 `session_id`。不代表 Python 持久化会话。 |
| `query` | string | 是 | 用户当前输入。不能为空或纯空白。 |
| `chat_history` | array | 否 | Java 组装的历史对话。Python 只读。 |
| `user_context` | object | 否 | Java 组装的用户画像、身体数据和偏好。Python 只读。 |
| `candidates` | array | 否 | Java 推给 Python 的候选商品。第一阶段 Python 优先从这里推荐。 |
| `debug` | boolean | 否 | 调试开关，生产默认 `false`。 |

## 4. ChatHistoryItem

第一阶段使用“对话轮次”格式，而不是原始消息表格式。
Java 可以从 `assistant_message` 的 `role/content` 记录组装成这个结构。

```json
{
  "user_query": "我 175cm 70kg，想买一件日常穿的 T 恤",
  "assistant_answer": "建议优先选择 L 码。"
}
```

规则：

- 按时间从旧到新排序。
- 每个 item 表示一轮用户问题和助手回答。
- Java 应限制传入轮次数，第一阶段建议最多 10 轮。
- Python 只能读取历史用于追问解析，不能把它当作唯一事实源。

## 5. UserContext

```json
{
  "user_id": 10001,
  "height_cm": 175,
  "weight_kg": 70,
  "gender": "male",
  "preferred_fit": "regular",
  "preferred_styles": ["commute"],
  "preferred_colors": ["black", "navy"],
  "disliked_colors": [],
  "preferred_categories": ["外套"],
  "budget_min": 100,
  "budget_max": 400
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `user_id` | number/string/null | Java 用户 id。匿名会话可为空。 |
| `height_cm` | number/null | 身高，单位 cm。 |
| `weight_kg` | number/null | 体重，单位 kg。 |
| `gender` | string/null | 建议值：`male`、`female`、`unknown`。 |
| `preferred_fit` | string/null | 建议值：`loose`、`regular`、`slim`。 |
| `preferred_styles` | array | 风格偏好，例如 `commute`、`casual`、`sport`、`korean`、`minimal`。 |
| `preferred_colors` | array | 偏好颜色。 |
| `disliked_colors` | array | 不喜欢的颜色。 |
| `preferred_categories` | array | 偏好品类。 |
| `budget_min` | number/null | 预算下限，单位人民币元。 |
| `budget_max` | number/null | 预算上限，单位人民币元。 |

字段缺失时 Python 不猜测用户画像。需要画像才能继续时，应返回追问。

## 6. ProductCandidate

`candidates` 表示 Java 侧已经按商品、价格、库存、上架状态、用户预算等规则筛过的候选。
第一阶段推荐使用 SKU 级候选，便于 Python 返回可直接展示的商品卡片引用。

```json
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
  "main_image_url": "/images/products/jacket-commute-main.svg"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `spu_id` | number/string | 是 | 商品主体 id。 |
| `spu_code` | string/null | 否 | 商品主体编码。 |
| `sku_id` | number/string | 是 | 可售 SKU id。第一阶段推荐结果以 SKU 级候选为准。 |
| `sku_code` | string/null | 否 | SKU 编码。 |
| `name` | string | 是 | 商品名称。 |
| `category` | string/null | 否 | 商品分类。 |
| `brand` | string/null | 否 | 品牌。 |
| `color` | string/null | 否 | SKU 颜色。 |
| `size` | string/null | 否 | SKU 尺码。 |
| `sale_price` | number/null | 否 | 当前销售价。事实来源仍以 Java 为准。 |
| `stock_status` | string/null | 否 | 建议值：`in_stock`、`low_stock`、`out_of_stock`、`unknown`。 |
| `available_stock` | number/null | 否 | 可售库存。仅用于导购说明，不作为下单承诺。 |
| `material` | string/null | 否 | 材质。 |
| `fit_type` | string/null | 否 | 版型。 |
| `season` | array | 否 | 适用季节。 |
| `style_tags` | array | 否 | 风格标签。 |
| `main_image_url` | string/null | 否 | 商品主图，供 Java/前端展示。 |

规则：

- 有 `candidates` 时，Python 只能从候选里产生 `product_refs`。
- Python 不得编造候选外商品 id。
- Python 可以根据 `user_context`、`query`、RAG 知识和候选字段生成推荐理由。
- Python 可以使用 `sale_price`、`stock_status` 做导购说明，但最终价格和库存仍由 Java 在展示、加购、下单时校验。

## 7. ProductFactProvider 策略

Python 内部后续应通过商品事实 provider 访问结构化商品数据，而不是直接耦合某一个文件或 API。

第一阶段优先级：

```text
RequestCandidatesProvider
-> JsonProductFactProvider
-> JavaApiProductFactProvider
```

说明：

- `RequestCandidatesProvider` 读取 Java 请求中的 `candidates`。
- `JsonProductFactProvider` 读取本地 demo/test JSON，保证 Python 独立开发和 CI 不依赖 Java 服务。
- `JavaApiProductFactProvider` 等 Java internal API 稳定后再接入，通过配置开关启用。

生产环境建议：

- 如果 Java 已传 `candidates`，Python 不主动拉 Java internal API。
- 如果 Java 未传 `candidates`，且生产配置禁用 JSON fallback，Python 可以给出泛化导购建议，但 `product_refs` 必须为空。

## 8. PythonChatResponse

```json
{
  "request_id": "req-20260528-001",
  "answer": "可以优先看通勤轻薄外套，黑色和藏青色都比较适合日常通勤。",
  "intent": "recommendation",
  "product_refs": [],
  "suggested_actions": []
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `request_id` | string | 是 | 原样返回 Java 传入的 `request_id`。 |
| `answer` | string | 是 | 用户可见回答。 |
| `intent` | string | 是 | Python 识别出的意图。 |
| `product_refs` | array | 是 | 本次回答引用的商品列表。无商品引用时为空数组。 |
| `suggested_actions` | array | 是 | 建议前端/Java 可展示的动作。无动作时为空数组。 |
| `debug` | object | 否 | 仅当请求 `debug=true` 时返回。 |

建议 intent 值：

```text
chat
unknown
size_recommendation
product_qa
policy_qa
recommendation
inventory_check
price_check
```

## 9. ProductRef

```json
{
  "spu_id": 1001,
  "sku_id": 2001,
  "reason": "符合通勤风格，颜色百搭，预算范围内。",
  "rank_score": 0.91
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `spu_id` | number/string | 是 | Java 商品主体 id。 |
| `sku_id` | number/string | 是 | Java SKU id。 |
| `reason` | string | 是 | 推荐理由，应能被 Java 保存到推荐明细。 |
| `rank_score` | number/null | 否 | Python 内部排序分，范围建议 `0.0` 到 `1.0`。 |

规则：

- `product_refs` 必须来自 `candidates` 或启用的 provider。
- `reason` 必须能追溯到允许的证据，例如候选商品库存、尺码、颜色、价格、季节、风格标签、用户预算或用户颜色偏好；不得编造折扣、库存承诺、物流承诺或售后政策。
- `rank_score` 只是推荐排序参考，不代表业务优先级或交易承诺。
- Python 返回多个商品时应按推荐优先级排序。

## 10. SuggestedAction

```json
{
  "type": "view_product",
  "spu_id": 1001,
  "sku_id": 2001
}
```

第一阶段 action type：

| type | 说明 | 字段要求 |
| --- | --- | --- |
| `view_product` | 查看商品详情或商品卡片 | `spu_id`、`sku_id` |
| `add_to_cart` | 加入购物车 | `spu_id`、`sku_id` |
| `buy_now` | 立即购买 | `spu_id`、`sku_id` |
| `ask_follow_up` | 需要用户补充信息 | 可不带商品 id |

规则：

- `add_to_cart` 和 `buy_now` 只是建议动作，实际执行必须由 Java 完成鉴权、库存和价格校验。
- 缺信息场景应优先返回 `ask_follow_up`。

## 11. 缺信息响应

用户缺少商品、颜色、尺码、预算或身体数据时，Python 应返回追问。

示例：

```json
{
  "request_id": "req-20260528-002",
  "answer": "想查哪件商品？请补充商品名或 SKU，我再帮你查库存或价格。",
  "intent": "inventory_check",
  "product_refs": [],
  "suggested_actions": [
    {
      "type": "ask_follow_up"
    }
  ]
}
```

规则：

- 缺关键信息时不调用大模型猜测。
- 缺商品时不返回商品引用。
- 缺颜色或尺码时不返回库存结论。

## 12. 无候选商品响应

生产环境中，如果 Java 没有传 `candidates`，且 Python 没有启用生产事实 provider，Python 不应编造商品引用。

```json
{
  "request_id": "req-20260528-003",
  "answer": "可以按通勤、低饱和颜色、合身版型来筛选外套。当前没有可用商品候选，我先不推荐具体商品。",
  "intent": "recommendation",
  "product_refs": [],
  "suggested_actions": []
}
```

## 13. Debug 字段边界

当 `debug=false` 时，响应不得包含内部 trace、检索 chunk、prompt 或工具原始输出。

`/chat/stream` 面向 Java 转发链路，当前 done 事件不暴露 `debug`、`trace_events`、`selected_tools` 等内部字段。即使请求体里带 `debug=true`，流式输出也必须保持前端可见字段边界。

当 `debug=true` 时，Python 可以返回：

- `thread_id`
- `intent_result`
- `selected_tools`
- `missing_info_result`
- `structured_result`
- `accepted_chunks`
- `rejected_chunks`
- `validation_result`
- `trace_events`

Debug 只用于开发、联调、评测和排障，不应暴露给普通用户。

## 14. 技术错误响应

参数校验错误使用 HTTP `422`。

未捕获异常使用 HTTP `500`，生产环境不得暴露内部堆栈。

```json
{
  "error": "internal_server_error",
  "request_id": "req-20260528-004",
  "message": "AI service failed to process the request."
}
```

业务降级不要使用 `500`。例如无候选、知识库无证据、缺信息，都应返回 HTTP `200` 和可解释回答。

## 15. 推荐闭环保存

Java 收到 `PythonChatResponse` 后建议保存：

- `assistant_message.content` = `answer`
- `assistant_message.intent` = `intent`
- `assistant_recommendation.query` = 请求 `query`
- `assistant_recommendation.answer` = `answer`
- `assistant_recommendation.source` = `python_agent`
- `assistant_recommendation_item.spu_id`
- `assistant_recommendation_item.sku_id`
- `assistant_recommendation_item.reason`
- `assistant_recommendation_item.rank_score`
- `ai_request_log.request_id`
- `ai_request_log.status`
- `ai_request_log.latency_ms`

Python 不负责保存这些表，只负责返回可保存的结构化结果。

## 16. 2026-06-19 流式接口回归边界

本轮新增 Python 侧回归点：

- `/chat/stream` 的 `data:` 行必须是单行 JSON，便于 Java SSE parser 稳定解析。
- `done` 事件保留 `request_id`、`answer`、`intent`、`product_refs`，其中 `product_refs` 必须来自候选数据或允许的事实 provider。
- 流式输出不得包含 `debug`、`trace_events`、`selected_tools` 等内部调试字段。
- Python 生成 `product_refs` 时跳过候选池外、缺少 `spu_id`/`sku_id`、以及重复的候选引用。
- Python 生成的 `reason` 现在覆盖库存可见、尺码、风格/季节/场景匹配、预算匹配和颜色偏好匹配，并通过 `tests.test_recommendation_service` 回归。

本轮验证命令：

```bash
.venv/bin/python -m unittest tests.test_chat_stream tests.test_recommendation_service -v
```
