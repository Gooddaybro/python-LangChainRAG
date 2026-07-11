# 数据边界设计

本文档说明当前项目里“哪些数据应该查结构化数据，哪些数据应该走 RAG，哪些数据只是调试和会话控制”。这是后续扩展商品库、替换数据库、增强 memory 和部署生产环境时的边界契约。

## 1. 目标

服装导购 Agent 不能把所有问题都交给向量检索或大模型。生产级项目必须区分：

```text
精确事实 -> 结构化数据
解释性知识 -> RAG
对话控制 -> LangGraph state / checkpointer
调试证据 -> trace/debug
最终表达 -> answer_generator + answer_validator
```

这个边界的核心原则是：

```text
价格、库存、SKU、颜色列表、尺码规则 id 不能靠 RAG 猜。
颜色搭配、洗涤养护、风格场景建议可以通过 RAG 检索解释。
```

## 2. 数据来源总览

| 数据来源 | 当前文件或模块 | 负责内容 | 使用节点 |
| --- | --- | --- | --- |
| 商品目录 | `clothing_assistant/data/product_catalog.json` | 商品、SKU、价格、库存、颜色、尺码规则 id、政策 id | `structured_lookup` |
| 商品知识文件 | `clothing_assistant/data/*.txt` | 颜色、洗涤、尺码、场景、材质、版型的解释性知识 | `rag_retriever` |
| 向量库 | `clothing_assistant/chroma_db/` | 文本 chunk 的向量索引 | `rag_tool` |
| 请求历史 | API 请求里的 `chat_history` | 当前追问需要的显式历史 | `context_resolver` |
| LangGraph checkpoint | 当前为 `InMemorySaver` | 按 `thread_id` 保存图执行状态 | LangGraph runtime |
| trace/debug | `trace_events` 和可选本地 JSONL | 节点路径、工具结果、证据摘要 | `trace_logger` |

## 3. 结构化数据边界

结构化数据负责所有必须精确、可校验、可追责的业务事实。

当前结构化数据文件：

```text
clothing_assistant/data/product_catalog.json
```

当前商品字段：

```json
{
  "sku": "TS-BASIC-001",
  "product_id": "TSHIRT_BASIC_001",
  "name": "基础款纯棉T恤",
  "category": "T恤",
  "material": "100%纯棉",
  "price_cny": 99,
  "size_rule_id": "default_tshirt",
  "policy_id": "standard_apparel",
  "colors": [
    {"name": "黑色", "stock": {"S": 6, "M": 12, "L": 8, "XL": 0}}
  ],
  "aliases": ["T恤", "纯棉T恤", "基础T", "基础款T恤"]
}
```

必须走结构化查询的问题：

| 问题类型 | 示例 | 原因 |
| --- | --- | --- |
| 库存 | `基础款纯棉T恤黑色L码有货吗？` | 库存是实时/准实时事实，不能由模型猜 |
| 价格 | `基础款纯棉T恤多少钱？` | 价格必须和目录一致 |
| SKU / 商品 id | `TS-BASIC-001 是哪件？` | 商品身份必须精确 |
| 可选颜色 | `这件 T 恤有哪些颜色？` | 颜色列表来自商品目录 |
| 尺码规则 id | `这件衣服用哪个尺码规则？` | 不同商品可能绑定不同尺码规则 |
| 政策 id | `这件商品适用什么售后规则？` | 后续可接结构化政策表 |

结构化查询节点输出应该包含：

```json
{
  "lookup_type": "inventory",
  "matched_product_id": "TSHIRT_BASIC_001",
  "matched_product_name": "基础款纯棉T恤",
  "color": "黑色",
  "size": "L",
  "stock_count": 8,
  "in_stock": true,
  "missing_fields": [],
  "reason": "库存来自 product_catalog.json。"
}
```

生产要求：

- 库存回答必须包含 `stock_count` 或明确说明无货/缺字段。
- 价格回答必须来自 `price_cny`。
- 商品匹配不唯一时必须追问，不能任选一个。
- 颜色或尺码缺失时必须进入 `missing_info_gate`。
- 结构化数据字段变化时，需要同步更新测试和本文档。

## 4. RAG 数据边界

RAG 负责解释性、语义型、非强一致的知识。

适合 RAG 的问题：

| 问题类型 | 示例 | 说明 |
| --- | --- | --- |
| 颜色搭配 | `日常通勤推荐什么颜色？` | 需要结合风格和场景解释 |
| 洗涤养护 | `纯棉T恤怎么洗？` | 需要知识说明 |
| 风格推荐 | `这件适合通勤吗？` | 需要场景判断 |
| 季节适配 | `这件衣服适合夏天吗？` | 需要材质和穿着知识 |
| 材质解释 | `纯棉有什么特点？` | 需要解释，不是库存事实 |

不适合 RAG 的问题：

| 问题类型 | 原因 |
| --- | --- |
| 价格 | 价格必须精确，且可能变化 |
| 库存 | 库存必须精确，且可能变化 |
| SKU 匹配 | SKU 是结构化标识 |
| 可购买尺码 | 需要查商品库存 |
| 售后政策生效条件 | 后续应接结构化政策表 |

RAG 检索后必须经过：

```text
retrieval_grader
```

当前评分规则：

- 分数高于距离阈值 `0.25` 的 chunk 会被拒绝。
- 来源文件不符合 `query_type` 的 chunk 会被拒绝。
- 没有 `accepted_chunks` 时，`retrieval_grader` 之后直接进入 `fallback_answer` 保守兜底。
- 最终回答只追加 `accepted_chunks` 的文件名和 `chunk_id`，不让模型自行编造引用。
- 纯 RAG 草稿不能断言价格、库存、SKU、上/下架状态；命中这些模式时重试一次，
  仍失败则进入保守兜底。

## 5. Memory 边界

当前状态：

```text
chat_history 显式从 API 请求传入
thread_id 用于 LangGraph checkpoint/debug
```

也就是说，现在追问可靠性主要依赖调用方传入 `chat_history`。例如：

```json
{
  "query": "那我想宽松一点呢？",
  "chat_history": [
    {
      "user_query": "我身高178，体重65kg，想买T恤",
      "assistant_answer": "建议选择 L 码。"
    }
  ],
  "thread_id": "api-test-001"
}
```

后续生产化方向：

- 让 `thread_id` 绑定短期对话 memory。
- 使用数据库 checkpointer 替代 `InMemorySaver`。
- 明确哪些 state 字段可以跨轮保留，哪些字段只属于单次请求。
- 避免把完整用户隐私长期写入 trace 或日志。

## 6. Trace 和 Debug 边界

`debug=true` 用于开发、测试、eval 和排障。生产普通用户默认应使用：

```json
{
  "debug": false
}
```

debug 可包含：

- `intent_result`
- `selected_tools`
- `structured_result`
- `accepted_chunks`
- `rejected_chunks`
- `validation_result`
- `evidence_summary`
- `trace_events`

debug 不应该长期公开给普通用户，因为它可能暴露：

- 内部节点路径
- 商品目录细节
- 检索 chunk 内容
- 工具执行摘要
- 未来可能包含的用户历史信息

生产日志要求：

- 不记录 API key。
- 不记录完整隐私数据。
- trace 落盘必须可开关。
- trace 落盘已默认关闭；显式启用时会对明显的 `Authorization: Bearer ...`、`api_key=...`、`token=...`、`password=...`、`secret=...` 片段做脱敏。
- 错误日志应有 request id 或 run id。
- 对外 `500` 响应不应暴露内部堆栈。

## 7. 失败行为边界

| 场景 | 当前行为 | 生产原则 |
| --- | --- | --- |
| 缺商品 | `missing_info_gate` 追问商品名或 SKU | 不猜商品 |
| 缺颜色/尺码 | `missing_info_gate` 追问颜色或尺码 | 不猜库存 |
| 价格查询无商品 | `missing_info_gate` 追问商品 | 不返回模糊价格 |
| RAG 弱证据 | `fallback_answer` 保守兜底 | 不编造解释 |
| 政策无来源 | `policy_fallback` 引导人工确认 | 不编造售后规则 |
| 无法识别意图 | `direct_answer_gate` 引导补充范围 | 不进入工具链 |

## 8. 测试边界

确定性测试负责验证“走对路”：

```text
tests/test_product_catalog.py
tests/test_langgraph_production_nodes.py
tests/test_langgraph_shadow.py
tests/test_agent_eval_cases.py
tests/test_eval_report.py
```

应该覆盖：

- 缺信息是否追问。
- 库存是否只走 `structured_lookup`。
- 价格是否只来自 `product_catalog.json`。
- RAG 是否经过 `retrieval_grader`。
- 弱检索是否触发 `answer_fallback`。
- debug 是否暴露结构化证据。

运行：

```powershell
python -m unittest tests.test_product_catalog -v
python -m unittest tests.test_langgraph_production_nodes -v
python -m unittest discover -v
```

## 9. 后续演进

推荐顺序：

1. 为 `product_catalog.json` 增加 JSON schema 校验。
2. 把商品目录迁移到 SQLite，保留当前查询函数作为适配层。
3. 增加结构化政策表，例如 `policy_catalog.json`。
4. 把 `thread_id` 和短期 memory 绑定到数据库 checkpointer。
5. 增加 `docs/eval-plan.md`，把路由评测和答案质量评测分开。
6. 增加数据重建文档，说明知识库和向量库如何刷新。
7. 增加生产日志、鉴权、限流和部署说明。
