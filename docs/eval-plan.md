# 评测设计

本文档定义当前项目的评测体系。目标是把“路由和工具是否走对”与“最终答案质量是否足够好”分开，避免用一套测试同时承担两种不同职责。

## 1. 评测目标

生产级 RAG / LangGraph 项目至少需要回答两个问题：

```text
1. 系统是否走对流程？
2. 最终答案是否可靠、完整、符合业务边界？
```

第一类问题适合确定性测试。第二类问题适合答案质量评测。

当前项目已经有确定性评测基础：

```text
clothing_assistant/agent/eval_cases.py
clothing_assistant/agent/eval_report.py
tests/test_agent_eval_cases.py
tests/test_langgraph_shadow.py
tests/test_langgraph_production_nodes.py
tests/test_eval_report.py
```

下一步要补的是独立的答案质量评测。

## 2. 两类评测的边界

| 评测类型 | 主要问题 | 是否依赖真实模型 | 是否要求输出文本质量 |
| --- | --- | --- | --- |
| 确定性路由/工具评测 | 意图、工具、停止原因、证据来源是否正确 | 否 | 否 |
| 答案质量评测 | 答案是否有用、准确、完整、不过界 | 可以依赖 | 是 |

不要把这两类混在一起。

如果一个 case 的目标是检查：

```text
selected_tools == ["structured_lookup"]
stop_reason == "final_answer"
```

它属于确定性评测。

如果一个 case 的目标是检查：

```text
答案必须说明黑色 L 码有货，库存 8 件，不能说 XL 有货
```

它属于答案质量评测。

## 3. 当前确定性评测

当前 `EVAL_CASES` 主要验证 Agent 调度契约：

```text
expected_intent
expected_tools
expected_stop_reason
requires_rag
```

示例：

```python
{
    "name": "inventory_exact_black_l_langgraph",
    "query": "基础款纯棉T恤黑色L码有货吗？",
    "executors": ["langgraph"],
    "expected_intent": INTENT_INVENTORY_CHECK,
    "expected_tools": ["structured_lookup"],
    "expected_stop_reason": "final_answer",
    "requires_rag": False,
}
```

这类 case 不评判最终回答写得是否自然，只判断流程和工具是否正确。

当前覆盖范围：

- 闲聊直答
- 越界问题
- 政策兜底
- 尺码推荐
- 历史追问
- 商品语义 RAG
- 库存缺信息
- 库存精确查询
- 价格精确查询
- 结构化查询和 RAG 分流

## 4. 当前评测运行方式

运行确定性单测：

```powershell
python -m unittest tests.test_agent_eval_cases -v
python -m unittest tests.test_langgraph_shadow -v
python -m unittest tests.test_langgraph_production_nodes -v
python -m unittest tests.test_eval_report -v
```

运行全部测试：

```powershell
python -m unittest discover -v
```

生成评测报告：

```powershell
python -m clothing_assistant.agent.eval_report
```

当前 `eval_report` 使用 fake tools，目的是让评测聚焦于路由、工具选择和停止原因，不受真实向量库、大模型或网络状态影响。

## 5. 确定性评测扩展计划

目标：从当前 22 个 case 扩到 30+ 个真实业务 case。

新增 case 应该覆盖：

| 类型 | 示例 | 预期 |
| --- | --- | --- |
| 缺商品 | `黑色M码有货吗？` | `missing_info` |
| 缺颜色 | `基础款纯棉T恤L码有货吗？` | `missing_info` |
| 缺尺码 | `基础款纯棉T恤黑色有货吗？` | `missing_info` |
| 精确库存 | `基础款纯棉T恤黑色L码有货吗？` | `structured_lookup` |
| 无货库存 | `基础款纯棉T恤黑色XL码有货吗？` | `structured_lookup` |
| 不存在颜色 | `基础款纯棉T恤红色M码有货吗？` | `structured_lookup` |
| 精确价格 | `基础款纯棉T恤多少钱？` | `structured_lookup` |
| 多商品价格 | `通勤轻薄外套价格是多少？` | `structured_lookup` |
| 语义颜色 | `日常通勤推荐什么颜色？` | `rag_tool` |
| 洗涤养护 | `纯棉T恤怎么洗？` | `rag_tool` |
| 弱检索 | fake weak chunks | `answer_fallback` |
| 政策无来源 | `可以退货吗？` | `policy_fallback` |
| 历史追问 | `那我想宽松一点呢？` | `size_tool` |
| 越界问题 | `帮我写一首诗` | `direct_answer` |

每个确定性 case 至少包含：

```text
name
query
expected_intent
expected_tools
expected_stop_reason
requires_rag
```

如果只适用于 LangGraph 主线：

```python
"executors": ["langgraph"]
```

如果 pipeline 和 LangGraph 预期不同：

```python
"expected_by_executor": {
    "langgraph": {
        "expected_tools": ["structured_lookup"],
        "requires_rag": False
    }
}
```

## 6. 答案质量评测设计

答案质量评测应该独立于当前 `EVAL_CASES`。

建议新增文件：

```text
clothing_assistant/agent/answer_quality_cases.py
clothing_assistant/agent/answer_quality_report.py
tests/test_answer_quality_report.py
```

答案质量 case 推荐结构：

```python
{
    "name": "inventory_answer_mentions_exact_stock",
    "query": "基础款纯棉T恤黑色L码有货吗？",
    "chat_history": [],
    "must_include": ["基础款纯棉T恤", "黑色", "L", "8"],
    "must_not_include": ["XL有货", "可能", "大概"],
    "expected_grounding": "structured_lookup",
    "answer_type": "inventory",
}
```

答案质量评测关注：

- 是否回答了用户问题。
- 是否包含关键事实。
- 是否没有编造库存或价格。
- 是否在缺信息时追问。
- 是否在弱检索时保守兜底。
- 是否没有把 debug JSON 暴露给用户。
- 是否中文客服语气自然简洁。

## 7. 答案质量评分方式

第一阶段建议用确定性规则评分，不急着上 LLM judge。

规则评分字段：

```text
must_include
must_not_include
expected_grounding
expected_stop_reason
max_answer_length
```

示例评分：

| 检查项 | 通过条件 |
| --- | --- |
| 必须包含 | `must_include` 中每个词都出现在答案里 |
| 禁止包含 | `must_not_include` 中每个词都不能出现在答案里 |
| 证据来源 | `debug.selected_tools` 包含预期工具 |
| 停止原因 | `debug.stop_reason` 等于预期 |
| 长度 | 答案不超过设定字符数 |

第二阶段再考虑 LLM judge，用于判断表达自然度、信息完整性和客服语气。

LLM judge 不能替代确定性校验。库存、价格、缺信息、工具选择仍然必须用规则判断。

## 8. 报告格式

建议两个报告分开：

```text
python -m clothing_assistant.agent.eval_report
python -m clothing_assistant.agent.answer_quality_report
```

确定性报告字段：

```text
case
executor
expected_intent
actual_intent
expected_tools
actual_tools
expected_stop_reason
actual_stop_reason
requires_rag
rag_chunk_count
passed
```

答案质量报告字段：

```text
case
query
answer
must_include_passed
must_not_include_passed
grounding_passed
stop_reason_passed
length_passed
passed
failure_reasons
```

## 9. 质量门槛

在继续做生产功能前，建议设置最低门槛：

```text
确定性评测：100% 通过
答案质量规则评测：核心库存/价格/缺信息 case 100% 通过
弱检索和政策兜底：100% 通过
```

如果某个答案质量 case 失败，不应该通过改 prompt 随便压过去。应先判断失败原因：

```text
是路由错了？
是结构化查询错了？
是 RAG 证据弱？
是 generator 表达问题？
是 validator 没挡住？
```

再决定改节点、数据、检索还是 prompt。

## 10. 与生产节点的关系

评测应该直接覆盖节点边界：

| 节点 | 应覆盖的评测 |
| --- | --- |
| `intent_router` | intent 是否正确 |
| `context_resolver` | 是否正确使用历史 |
| `missing_info_gate` | 缺字段是否追问 |
| `structured_lookup` | 库存/价格是否精确 |
| `rag_retriever` | 语义问题是否检索 |
| `retrieval_grader` | 弱证据是否被拒绝 |
| `answer_generator` | 是否生成合适草稿 |
| `answer_validator` | 是否阻止无证据答案 |
| `trace_logger` | debug 是否保留证据摘要 |

如果新增节点，必须同步新增或调整 eval case。

## 11. 当前差距

当前已经具备：

- 基础确定性 eval case。
- pipeline 和 LangGraph 对照报告。
- LangGraph-only 生产节点 case。
- 结构化查询测试。
- 弱检索兜底测试。

仍然缺少：

- 独立答案质量 case 文件。
- 独立答案质量报告。
- 30+ 真实业务 case。
- 冲突证据 case。
- 更完整的历史追问 case。
- 面向 CI 的质量门槛说明。

## 12. 下一步执行顺序

推荐顺序：

1. 先把 `EVAL_CASES` 扩到 30+ 个确定性业务 case。
2. 新增 `answer_quality_cases.py`。
3. 新增 `answer_quality_report.py`。
4. 新增 `tests/test_answer_quality_report.py`。
5. 把 Streamlit Eval Report 区分为“路由/工具评测”和“答案质量评测”。
6. 在 README 里补充两个评测命令。
7. 后续再考虑 LLM judge。
