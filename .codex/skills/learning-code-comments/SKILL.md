---
name: learning-code-comments
description: Use when adding, reviewing, or improving comments and docstrings in this project while the user is learning Python Agent, RAG, ToolRegistry, AgentState, evaluation, or LangGraph migration concepts.
---

# Learning Code Comments

## Overview

这个 skill 只服务当前项目的学习阶段。目标不是增加注释数量，而是让注释帮助学习者理解 Agent 架构、数据流、边界设计、兜底策略和未来迁移到 LangGraph 的路径。

核心原则：注释解释“为什么这样做”和“这段代码在系统里承担什么责任”，不要解释 Python 语法或一眼能读懂的代码。

## Comment Rules

- 优先注释架构边界：`AgentState`、`ToolRegistry`、executor pipeline、LangGraph shadow、eval report、fallback 逻辑。
- 注释要靠近它解释的代码，不要把解释集中放到文件末尾。
- 中文教学注释可以比生产注释稍微详细，但仍然要短；一段注释通常不超过 3 行。
- 修改代码时同步更新旧注释。过期注释比没有注释更危险。
- 对临时学习提醒使用 `Learning:` 前缀，方便以后搜索和清理。

## Comment Types

### Module Docstring

用于复杂模块顶部，说明文件在项目架构中的位置。

```python
"""手写 MVP Agent 执行器。

这个模块是当前主线 pipeline，用来和 LangGraph shadow 做行为对照。
学习重点：AgentState 如何承载中间结果，ToolRegistry 如何收敛工具选择。
"""
```

### Function Docstring

用于核心函数，说明职责、输入输出和学习重点。普通小函数不用强行写。

```python
def run_agent(...):
    """执行一次手写 Agent 请求。

    这是当前生产主线，不依赖 LangGraph。
    返回的 trace_events 用于本地调试和评测报告对照。
    """
```

### Flow Comment

用于 pipeline、graph node、路由判断这类多阶段流程。

```python
# 阶段 1：先判断意图，再让 ToolRegistry 选择工具。
# 这里不直接执行工具，避免路由逻辑和工具执行重新耦合。
```

### Boundary Comment

用于解释兜底、重试、fake tool、质量门槛、死循环防护等边界。

```python
# policy_tool 查不到可靠来源时直接兜底，不进入生成阶段。
# 这样可以避免模型在缺少政策依据时编造退换货规则。
```

### Learning Note

用于学习阶段的关键提醒。它可以比普通注释更直白，但不要覆盖整段代码。

```python
# Learning: fake tools 不是业务逻辑，而是让评测稳定、可重复。
```

## Project-Specific Guidance

- `agent_executor.py`：重点解释 pipeline 阶段、状态更新、停止原因。
- `agent_state.py`：重点解释字段为什么存在，哪些字段接近 LangGraph state。
- `tool_registry.py`：重点解释工具声明、选择条件、返回结构。
- `langgraph_executor.py`：重点解释 node、edge、conditional route 和 shadow 对照目的。
- `eval_cases.py` / `eval_report.py`：重点解释固定评测为什么要确定性、为什么不依赖真实模型。

## Do Not Add

- 不要给简单赋值、明显循环、普通 import 加注释。
- 不要重复函数名或变量名已经表达清楚的内容。
- 不要写“调用函数”“返回结果”这种空注释。
- 不要用注释掩盖命名混乱；能改好名字时先改名字。
- 不要写和当前代码不一致的未来计划。未来迁移想法应写成明确学习提示或设计文档。

## Final Check

交付前快速检查：

- 注释是否解释了设计原因，而不是复述代码？
- 注释是否帮助学习 Agent/RAG/LangGraph，而不是讲 Python 基础语法？
- 注释是否靠近相关代码，并且不会在代码变化后马上过期？
- 是否有过多 `Learning:` 注释需要删减？
