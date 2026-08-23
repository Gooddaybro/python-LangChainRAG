# 代码注释风格指南

本文档定义本项目的代码注释标准。它服务于三类读者：AI 编程助手、项目开发者和代码 review 人。

## 1. 注释目标

注释应该解释系统边界、业务原因和数据流，而不是翻译代码。

好的注释回答：

```text
这个模块承担什么责任？
这个函数的输入、输出和失败边界是什么？
这里为什么需要 fallback、验证或分流？
这段逻辑和 AgentState、LangGraph、RAG、ToolRegistry 的关系是什么？
```

不好的注释通常只是重复代码：

```python
# Loop over items.
for item in items:
    ...
```

## 2. Docstring 风格

项目统一使用 Google Style Python Docstrings。

公共函数模板：

```python
def function_name(arg: str, limit: int = 10) -> list[str]:
    """Summarize the function responsibility in one short sentence.

    Add one short paragraph when the function owns an important business
    boundary, data-flow decision, or integration contract.

    Args:
        arg: Business meaning of the argument.
        limit: Maximum number of results to return.

    Returns:
        A list of result strings ordered by relevance.

    Raises:
        ValueError: If the input violates a business constraint.
    """
```

## 3. 模块注释

复杂模块顶部应该说明它在系统中的位置。

适合写模块 Docstring 的文件：

```text
clothing_assistant/agent/langgraph_executor.py
clothing_assistant/agent/nodes.py
clothing_assistant/agent/state.py
clothing_assistant/agent/tool_registry.py
clothing_assistant/api/app.py
clothing_assistant/api/schemas.py
```

示例：

```python
"""LangGraph production workflow entrypoint.

This module wires the clothing assistant's deterministic routing, structured
lookup, RAG retrieval, answer validation, and trace logging nodes into the
runtime graph used by the FastAPI `/chat` endpoint.
"""
```

## 4. 函数注释

公共函数必须写 Docstring。内部小函数如果只是局部实现细节，可以不强制写，但名称必须清楚。

合格示例：

```python
def run_langgraph_agent(
    query: str,
    chat_history: list[dict[str, str]] | None = None,
    thread_id: str | None = None,
    debug: bool = False,
) -> dict[str, object]:
    """Run one user request through the production LangGraph workflow.

    The function is the public Python entrypoint behind the FastAPI `/chat`
    route. It keeps trace data available for local evaluation while returning
    a user-facing answer for normal callers.

    Args:
        query: User question from the API or local workbench.
        chat_history: Explicit conversation history supplied by the caller.
        thread_id: Optional conversation id used by checkpoint/debug config.
        debug: Whether to include internal trace data in the returned payload.

    Returns:
        A result dictionary containing the final answer and optional debug data.
    """
```

不合格示例：

```python
def run_langgraph_agent(query):
    """Run langgraph agent."""
```

问题：

```text
没有类型提示
没有输入输出约束
没有说明它是生产入口
没有说明 debug 数据边界
```

## 5. 行内注释

行内注释只在逻辑不容易从代码本身读出时使用。

适合写行内注释的位置：

```text
LangGraph 条件边
缺失信息追问
结构化查询和 RAG 分流
弱证据 fallback
eval fake tool 或确定性替身
防止模型编造事实的校验逻辑
```

示例：

```python
# Inventory and price must stay on structured data so the model cannot invent
# product facts when the catalog has no matching SKU.
if intent in EXACT_FACT_INTENTS:
    return "structured_lookup"
```

## 6. Pydantic 字段说明

外部 API Schema 的字段必须使用 `Field(description=...)` 描述业务含义。

示例：

```python
class PythonChatRequest(BaseModel):
    request_id: str = Field(..., min_length=1, description="Caller-provided request id.")
    query: str = Field(..., min_length=1, description="Current user question.")
```

如果字段只是内部测试夹具或私有中间结构，可以不强制提供 `description`，但命名必须清楚。

## 7. Agent / RAG / LangGraph 专项规则

`AgentState` 注释重点：

```text
字段为什么存在
哪个节点写入它
它是否进入 debug/eval 输出
它是否接近未来 LangGraph reducer 或 checkpoint 状态
```

LangGraph 节点注释重点：

```text
节点读取哪些字段
节点写入哪些字段
什么情况下停止
什么情况下进入下一个节点
```

RAG 注释重点：

```text
RAG 能回答解释性知识
RAG 不能回答库存、价格、SKU 等精确事实
弱证据时必须 fallback
```

Eval 注释重点：

```text
为什么使用 fake tool
为什么不依赖真实向量库、真实模型或网络
case 检查的是路由/工具还是最终答案质量
```

## 8. 本地检查命令

安装开发依赖：

```powershell
python -m pip install -r requirements-dev.txt
```

运行质量检查：

```powershell
ruff check clothing_assistant tests
interrogate -v -i --fail-under=30 clothing_assistant
```

运行基础验证：

```powershell
python -m compileall -q clothing_assistant tests
python -m pytest -q
```

安装 pre-commit：

```powershell
pre-commit install
pre-commit run --all-files
```

## 9. Review 标准

Review 注释时优先检查：

```text
注释是否解释业务边界，而不是重复代码
Docstring 是否和当前代码一致
类型提示是否完整
Pydantic 字段是否有 description
RAG 和结构化数据边界是否写清楚
fallback 是否说明原因
```

不要为了通过覆盖率写低价值注释。宁可先降低阈值并记录债务，也不要把无意义 Docstring 合入主线。
