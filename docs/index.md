# AI Clothing Shopping Assistant System

这是服装电商导购和客服场景的 Python AI 助手项目文档站点。

核心内容：

```text
FastAPI HTTP API
LangGraph 生产工作流
结构化商品查询
RAG 解释性知识检索
确定性评测和质量门禁
答案质量评测
代码注释与文档约束体系
```

常用本地命令：

```powershell
python -m pytest -q
python -m compileall -q clothing_assistant tests
ruff check clothing_assistant tests
interrogate -v -i --fail-under=30 clothing_assistant
mkdocs serve
```

如果只想了解注释和文档规则，先阅读：

```text
代码注释与文档约束体系
代码注释风格指南
```

如果要继续补齐 AI 回答可靠性，先阅读：

```text
评测设计
答案质量评测落地计划
```

常用评测命令：

```powershell
python -m clothing_assistant.agent.eval_report
python -m clothing_assistant.agent.answer_quality_report
```
