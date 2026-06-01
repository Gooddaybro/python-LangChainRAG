# 代码注释与文档约束体系设计

本文档定义 `AI Clothing Shopping Assistant System` 的代码注释、团队文档和工具拦截方案。目标不是一次性给所有历史代码补满注释，而是先建立可执行的规则，让后续 AI 辅助开发、人工 review、CI 检查都围绕同一套标准工作。

## 1. 建设目标

当前项目已经包含 FastAPI、Streamlit、RAG、LangGraph、Agent 节点、工具注册和评测报告等模块。随着代码继续增长，注释和文档需要承担三个职责：

```text
帮助 AI 生成符合规范的新代码
帮助开发者理解模块边界和业务约束
帮助工具在 commit 和 PR 阶段拦截低质量变更
```

本体系分为三层：

| 层级 | 目标 | 主要产物 |
| --- | --- | --- |
| AI 编码约束层 | 让 AI 默认生成符合项目风格的注释和类型提示 | `.cursorrules`, `.github/copilot-instructions.md` |
| 团队文档层 | 让开发者知道什么是合格注释，并能生成 API 文档 | `docs/STYLE_GUIDE.md`, `mkdocs.yml`, API 文档入口 |
| 工具拦截层 | 在本地 commit 和 PR 阶段强制检查注释质量 | `pyproject.toml`, `.pre-commit-config.yaml`, GitHub Actions |

优先顺序建议为：

```text
工具拦截层
-> AI 编码约束层
-> 团队文档层
```

工具拦截层先落地，可以马上阻止新代码继续扩大注释债务。AI 约束层用于提高生成质量，团队文档层用于沉淀长期协作规范和 API 文档。

## 2. 注释总体原则

项目统一采用 Google Style Python Docstrings。注释关注设计原因、业务边界和数据流，不重复解释 Python 语法。

合格注释应回答：

```text
这个模块在系统里负责什么？
这个函数的输入、输出和失败边界是什么？
这里为什么要这样设计，而不是直接调用模型或工具？
这段逻辑和 RAG / LangGraph / AgentState / ToolRegistry 的关系是什么？
```

不合格注释包括：

```text
把函数名翻译成中文
解释显而易见的赋值、循环和 if 判断
写和当前代码不一致的未来计划
用大段注释掩盖命名不清或职责混乱
```

## 3. AI 编码约束层

### 3.1 目标

AI 编程助手生成或修改代码时，应默认遵守本项目的注释、类型和文档要求。这个层级不是强制门禁，但可以显著减少后续人工 review 的返工。

### 3.2 推荐文件

```text
.cursorrules
.github/copilot-instructions.md
```

`.cursorrules` 面向 Cursor、cline 等读取根目录规则的 AI 工具。

`.github/copilot-instructions.md` 面向 GitHub Copilot Chat 和 GitHub 代码协作场景。

### 3.3 核心规则

AI 生成 Python 代码时必须遵守：

- 使用 Google Style Python Docstrings。
- 模块、类、公共函数必须包含 Docstring。
- 公共函数 Docstring 包含 `Args:`, `Returns:`，有明确异常时包含 `Raises:`。
- 所有函数参数和返回值必须包含 Type Hints。
- Pydantic `Field` 必须提供 `description`，除非字段只用于内部测试夹具。
- 复杂业务逻辑需要行内注释解释设计原因。
- 注释优先解释 `AgentState`、LangGraph 节点流转、RAG 证据边界、ToolRegistry 工具选择、fallback 策略和 eval 稳定性。
- 不给简单赋值、普通 import、显而易见的循环添加噪音注释。

### 3.4 项目特定要求

对本项目，AI 还需要特别遵守：

| 模块 | 注释重点 |
| --- | --- |
| `clothing_assistant/agent/state.py` | 字段为什么存在，哪些字段接近 LangGraph state，哪些字段用于 debug/eval |
| `clothing_assistant/agent/nodes.py` | 每个节点的输入、输出、停止条件和业务边界 |
| `clothing_assistant/agent/langgraph_executor.py` | 图结构、条件边、checkpoint/debug 配置 |
| `clothing_assistant/agent/agent_executor.py` | 旧 pipeline 与 LangGraph 主线的迁移对照 |
| `clothing_assistant/agent/tool_registry.py` | 工具声明、选择条件和返回结构 |
| `clothing_assistant/tools/*.py` | 工具是否允许回答精确事实，是否只能返回证据 |
| `clothing_assistant/api/schemas.py` | API 字段含义、外部调用约束、Pydantic 字段描述 |
| `clothing_assistant/agent/eval_*.py` | 评测为什么要确定性、为什么不依赖真实模型或网络 |

## 4. 团队文档层

### 4.1 目标

团队文档层用于建立人类开发者共识。它说明什么代码需要注释、什么注释应该被拒绝，以及如何从 Docstrings 生成可阅读的 API 文档。

### 4.2 推荐文件

```text
docs/STYLE_GUIDE.md
mkdocs.yml
docs/api-reference.md
docs/api/agent.md
docs/api/tools.md
docs/api/http.md
```

如果后续希望把贡献流程也写清楚，可以新增：

```text
CONTRIBUTING.md
```

### 4.3 `docs/STYLE_GUIDE.md` 内容结构

建议包含：

```text
1. 注释目标
2. Google Style Docstring 模板
3. 模块 / 类 / 函数注释示例
4. 行内注释示例
5. Pydantic Field(description=...) 示例
6. RAG / LangGraph / Agent 专项注释规则
7. 不合格注释示例
8. 本地检查命令
```

好的函数 Docstring 示例：

```python
def run_langgraph_agent(
    query: str,
    chat_history: list[dict[str, str]] | None = None,
    thread_id: str | None = None,
    debug: bool = False,
) -> dict[str, object]:
    """Run one user request through the production LangGraph workflow.

    The function is the public Python entrypoint behind the FastAPI `/chat`
    route. It keeps debug trace data available for local evaluation while
    returning a user-facing answer for normal callers.

    Args:
        query: User question from the API or local workbench.
        chat_history: Explicit conversation history supplied by the caller.
        thread_id: Optional conversation id used by LangGraph checkpoint/debug config.
        debug: Whether to include internal trace data in the returned payload.

    Returns:
        A result dictionary containing the final answer and, when requested,
        debug fields used by tests and eval reports.
    """
```

不合格示例：

```python
def run_langgraph_agent(query):
    """Run langgraph agent."""
```

问题：

```text
没有说明它是生产入口
没有输入输出约束
没有说明 debug 数据的边界
没有类型提示
```

### 4.4 MkDocs 文档生成

推荐使用：

```text
mkdocs
mkdocs-material
mkdocstrings[python]
```

第一阶段只生成核心 API 文档，不需要覆盖所有模块：

```text
clothing_assistant.agent.langgraph_executor
clothing_assistant.agent.nodes
clothing_assistant.agent.state
clothing_assistant.tools.product_catalog
clothing_assistant.api.app
clothing_assistant.api.schemas
```

这样可以先让生产主线、工具边界和 HTTP API 有可读文档，再逐步扩展到其他模块。

## 5. 工具拦截层

### 5.1 目标

工具拦截层是硬性守门员。即使开发者或 AI 没有主动遵守规范，本地 commit 和 CI 也应该能拦截明显缺失 Docstring、Docstring 风格错误和注释覆盖率不足的问题。

### 5.2 Ruff 配置

推荐在 `pyproject.toml` 中添加 Ruff 配置：

```toml
[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "D", "UP", "B"]
ignore = [
    "D100",
    "D104",
]

[tool.ruff.lint.pydocstyle]
convention = "google"
```

说明：

- `D` 开启 pydocstyle Docstring 检查。
- `D100` 模块 Docstring 可在初期暂时放宽，避免历史文件一次性爆炸。
- `D104` 包 `__init__.py` Docstring 可在初期暂时放宽。
- 后续注释补齐后，可以逐步减少 ignore。

### 5.3 interrogate 注释覆盖率

推荐初期阈值不要直接设为 80。历史项目一次性切到 80 很容易阻塞正常开发。

当前项目历史基线约为 32.7%，因此第一阶段使用 30 作为可通过门槛。后续再按目录补齐 Docstring 后提升阈值。

建议节奏：

```text
第一阶段：fail-under = 30
第二阶段：fail-under = 60
第三阶段：fail-under = 70
第四阶段：fail-under = 80
```

建议命令：

```powershell
interrogate -v -i --fail-under=30 clothing_assistant
```

说明：

- `-v` 输出详细结果。
- `-i` 忽略 `__init__.py`。
- 先只检查 `clothing_assistant`，不检查 `tests`。

### 5.4 Pre-commit

推荐 `.pre-commit-config.yaml` 初始内容：

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.15
    hooks:
      - id: ruff
        args: [--fix]

  - repo: https://github.com/econchick/interrogate
    rev: 1.7.0
    hooks:
      - id: interrogate
        args: [-v, -i, --fail-under=30, clothing_assistant]
        pass_filenames: false
```

`pass_filenames: false` 的原因是 interrogate 更适合按包目录计算整体覆盖率，而不是只检查当前 commit 的少量文件。

### 5.5 GitHub Actions

推荐新增：

```text
.github/workflows/code-quality.yml
```

CI 应执行：

```powershell
python -m compileall -q clothing_assistant tests
ruff check clothing_assistant tests
interrogate -v -i --fail-under=30 clothing_assistant
python -m unittest discover -v
```

CI 的目标是防止有人绕过本地 pre-commit。PR 阶段检查失败时，不允许合并。

## 6. 分阶段落地计划

### 阶段 1：建立工具门禁

新增或修改：

```text
pyproject.toml
.pre-commit-config.yaml
.github/workflows/code-quality.yml
requirements-dev.txt
```

开发依赖建议单独放入 `requirements-dev.txt`：

```text
ruff
pre-commit
interrogate
mkdocs
mkdocs-material
mkdocstrings[python]
```

验收命令：

```powershell
python -m compileall -q clothing_assistant tests
python -m unittest discover -v
ruff check clothing_assistant tests
interrogate -v -i --fail-under=30 clothing_assistant
```

如果 Ruff 通用 lint 或格式化历史错误过多，阶段 1 先让 CI 只检查 Docstring 风格和覆盖率基线，再单独记录通用 lint/format 补齐任务。不要为了让工具通过而写大量低价值注释。

### 阶段 2：建立 AI 约束

新增：

```text
.cursorrules
.github/copilot-instructions.md
```

验收方式：

```text
新增一个小函数或 Pydantic Schema 时，AI 生成结果应自动带类型提示、Google Style Docstring 和 Field description。
人工 review 时不再重复解释基础注释规则，只检查业务边界是否准确。
```

### 阶段 3：建立团队规范文档

新增：

```text
docs/STYLE_GUIDE.md
```

可选新增：

```text
CONTRIBUTING.md
```

验收方式：

```text
开发者能通过文档判断一个 Docstring 是否合格。
review 反馈可以直接引用 STYLE_GUIDE 的章节。
```

### 阶段 4：接入 MkDocs

新增：

```text
mkdocs.yml
docs/api-reference.md
docs/api/agent.md
docs/api/tools.md
docs/api/http.md
```

验收命令：

```powershell
mkdocs build --strict
mkdocs serve
```

第一版文档站点只要求核心 API 能正常生成，不要求所有历史模块都有完整 API 页面。

## 7. 风险与处理策略

### 7.1 历史代码 Docstring 缺口过大

风险：

```text
一上来开启严格 D 规则和 80% 覆盖率，可能导致大量历史问题阻塞提交。
```

处理：

```text
先设置 60% 覆盖率。
暂时 ignore 少量历史压力最大的 D 规则。
只要求新增和重点模块逐步补齐。
```

### 7.2 注释数量增加但质量下降

风险：

```text
开发者为了通过工具，写大量“函数做了什么”的空注释。
```

处理：

```text
STYLE_GUIDE 明确坏例子。
AI 规则强调 Why 和业务边界。
review 重点检查注释是否解释设计原因。
```

### 7.3 MkDocs 暴露内部实验模块

风险：

```text
自动 API 文档如果全量扫描，可能把临时模块、旧 pipeline 或内部调试细节暴露成正式文档。
```

处理：

```text
第一阶段手动列出核心模块。
旧 pipeline 标明 migration/debug 用途。
临时模块不进入 API reference。
```

## 8. 推荐最终文件清单

本方案全部落地后，项目新增或修改文件如下：

```text
.cursorrules
.github/copilot-instructions.md
.github/workflows/code-quality.yml
.pre-commit-config.yaml
pyproject.toml
requirements-dev.txt
docs/STYLE_GUIDE.md
docs/code-documentation-governance.md
mkdocs.yml
docs/api-reference.md
docs/api/agent.md
docs/api/tools.md
docs/api/http.md
```

其中，本文档 `docs/code-documentation-governance.md` 是总体方案说明，不直接作为工具配置。

## 9. 建议执行顺序

如果本文档确认通过，建议下一步按以下顺序落地：

1. 新增 `requirements-dev.txt`，放入开发工具依赖。
2. 新增 `pyproject.toml`，配置 Ruff 和 interrogate。
3. 新增 `.pre-commit-config.yaml`，接入 Ruff 和 interrogate。
4. 运行本地检查，记录当前 Docstring 基线。
5. 新增 `.cursorrules` 和 `.github/copilot-instructions.md`。
6. 新增 `docs/STYLE_GUIDE.md`。
7. 新增 MkDocs 配置和第一批 API 文档页。
8. 新增 GitHub Actions，在 PR 阶段复跑质量检查。

阶段 1 完成后，不建议立即大规模补全所有历史 Docstring。更稳妥的方式是先保护新增代码，再针对 `agent`、`api`、`tools` 三个核心目录逐步提升覆盖率。
