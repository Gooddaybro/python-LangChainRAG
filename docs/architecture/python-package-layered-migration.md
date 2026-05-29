# Python 包分层迁移文档

## 1. 目标

本迁移只解决 Python AI 服务内部的包结构、依赖方向和运行时数据边界，不改变现有业务行为。

迁移完成后，项目应达到以下状态：

- 包名统一为 `clothing_assistant`，文档、测试、LangGraph 配置和启动命令不再引用旧包名 `clothing_rag_demo`。
- Streamlit 调试入口、FastAPI 接口、LangGraph 编排、领域规则、向量检索和本地文件存储有清晰边界。
- 运行时数据不再作为 Python package 的一部分被提交或维护。
- 旧 pipeline 保留为迁移对照入口，直到 LangGraph 主线完全稳定。
- 每一阶段都可以独立测试和回滚。

## 2. 非目标

本迁移不做以下事情：

- 不改 `/chat`、`/chat/pipeline`、`/chat/langgraph` 的对外 API 契约。
- 不改 LangGraph 节点业务语义。
- 不重写 RAG、尺码推荐、商品结构化查询算法。
- 不把本地 `product_catalog.json` 迁移到数据库。
- 不引入新的前端页面。
- 不删除旧手写 pipeline，除非后续单独批准。

## 3. 当前状态

当前代码已经部分完成从 `clothing_rag_demo` 到 `clothing_assistant` 的迁移：

```text
clothing_assistant/
├── api/                 # FastAPI 入口，已经存在
├── agent/               # LangGraph 与旧 pipeline，已经存在
├── tools/               # Agent 工具适配层，已经存在
├── app_qa.py            # Streamlit Agent 调试台，仍在包根目录
├── app_file_uploader.py # Streamlit 知识库上传页，仍在包根目录
├── rag.py               # 旧 RAG 编排与 LLM prompt 相关逻辑
├── size_matcher.py      # 尺码匹配规则，含文件读取
├── vector_stores.py     # 向量存储和 embedding 调用
├── knowledge_base.py    # 知识文件读取与切块
├── file_history_store.py# 本地聊天历史 JSONL 存储
└── config_data.py       # 路径常量和模型常量
```

主要结构债：

- `README.md`、`langgraph.json` 和多份 docs 仍残留 `clothing_rag_demo`。
- `app_qa.py`、`app_file_uploader.py` 这类 UI 入口仍在包根目录。
- `vector_stores.py`、`knowledge_base.py`、`file_history_store.py` 这类基础设施代码仍在包根目录。
- `size_matcher.py` 适合作为领域逻辑，但当前直接依赖文件路径配置并读本地 TXT。
- `chroma_db/`、`chat_history/`、`knowledge_file_hashes.json` 属于运行时数据，不应长期作为源码树内容。

## 4. 目标结构

目标采用轻量分层，不做过深目录嵌套：

```text
clothing_assistant/
├── api/
│   ├── app.py
│   └── schemas.py
│
├── ui/
│   ├── app_qa.py
│   └── app_file_uploader.py
│
├── agent/
│   ├── langgraph_executor.py
│   ├── nodes.py
│   ├── state.py
│   ├── router.py
│   ├── tool_registry.py
│   ├── agent_executor.py
│   ├── tracing.py
│   ├── eval_cases.py
│   └── eval_report.py
│
├── application/
│   ├── answer_service.py
│   └── rag_service.py
│
├── domain/
│   ├── size_matching.py
│   └── product_matching.py
│
├── infrastructure/
│   ├── knowledge_base.py
│   ├── vector_store.py
│   ├── file_history_store.py
│   └── llm_client.py
│
├── tools/
│   ├── memory_tool.py
│   ├── policy_tool.py
│   ├── product_catalog.py
│   ├── rag_tool.py
│   └── size_tool.py
│
├── config/
│   └── settings.py
│
└── data/
    ├── product_catalog.json
    ├── 尺码推荐.txt
    ├── 洗涤养护.txt
    └── 颜色选择.txt
```

说明：

- `api/` 当前已经清晰，先保留为顶层包，不强制搬到 `interfaces/api/`。
- `ui/` 只放 Streamlit 本地调试和演示入口。
- `agent/` 继续作为 LangGraph 主线和旧 pipeline 对照所在层。
- `application/` 只放跨 API、UI、Agent 可复用的用例编排和回答组装能力。
- `domain/` 放不依赖 FastAPI、Streamlit、向量库、LLM 客户端和文件系统的业务规则。
- `infrastructure/` 放文件系统、向量存储、embedding、LLM 客户端、本地 JSONL 历史等外部交互。
- `tools/` 是 Agent 工具适配层，可以依赖 `domain/` 和 `infrastructure/`，但不应反过来被它们依赖。

## 5. 依赖方向规则

允许的依赖方向：

```text
api/ui
  -> agent/application
  -> tools
  -> domain + infrastructure

agent/application
  -> tools
  -> domain + infrastructure

domain
  -> Python 标准库

infrastructure
  -> config
  -> 外部库或文件系统
```

禁止的依赖方向：

- `domain` 不依赖 `api`、`ui`、`agent`、`tools`、`infrastructure`。
- `infrastructure` 不依赖 `api`、`ui`、`agent`。
- `tools` 不依赖 Streamlit 或 FastAPI。
- `api` 不直接读写本地知识文件、向量库文件或聊天历史文件。

## 6. 分阶段迁移计划

### Phase 1: 包名和配置收口

目标：先把已经发生一半的 `clothing_assistant` 迁移收口。

预计改动：

- 修改 `README.md` 中的启动命令和说明。
- 修改 `langgraph.json` 中的 `dependencies` 和 `graphs` 路径。
- 修改 docs 中仍引用 `clothing_rag_demo` 的路径。
- 修改 `clothing_assistant/__init__.py` 的说明文字。
- 修正 `.gitignore` 中仍指向旧包名的运行时路径。

验证命令：

```powershell
python -m unittest tests.test_project_identity -v
python -m compileall -q clothing_assistant tests
```

通过标准：

- `tests.test_project_identity` 通过。
- `rg "clothing_rag_demo" README.md langgraph.json docs clothing_assistant tests` 不再命中有效运行路径。
- `langgraph.json` 指向 `./clothing_assistant/agent/langgraph_executor.py:get_default_langgraph_agent`。

### Phase 2: 运行时数据边界清理

目标：把运行时产物从源码边界中分离出来。

预计改动：

- `.gitignore` 忽略：
  - `clothing_assistant/chroma_db/`
  - `clothing_assistant/_chroma_probe/`
  - `clothing_assistant/_chroma_probe_segment/`
  - `clothing_assistant/chat_history/`
  - `clothing_assistant/traces/`
  - `clothing_assistant/knowledge_file_hashes.json`
- 从 Git 索引移除已跟踪的运行时文件，但保留本地文件。
- 文档说明这些文件如何重新生成。

后续可以再把默认运行时目录改到 `.local/clothing_assistant/` 或通过环境变量指定；本阶段先不改变运行路径，避免影响现有测试和本地启动。

验证命令：

```powershell
git ls-files | rg "chroma_db|chat_history|knowledge_file_hashes|simple_vector_store|\\.jsonl$"
python -m unittest discover -v
```

通过标准：

- `git ls-files` 不再列出运行时产物。
- 本地运行仍能按现有路径读写运行时文件。

### Phase 3: UI 入口迁移

目标：把 Streamlit 页面从包根目录移到 `ui/`。

预计改动：

- 移动 `clothing_assistant/app_qa.py` 到 `clothing_assistant/ui/app_qa.py`。
- 移动 `clothing_assistant/app_file_uploader.py` 到 `clothing_assistant/ui/app_file_uploader.py`。
- 增加短期兼容 wrapper：

```text
clothing_assistant/app_qa.py
clothing_assistant/app_file_uploader.py
```

wrapper 只负责从新路径导入 `main` 和测试需要的函数，避免一次性破坏现有测试与启动习惯。

需要同步更新：

- README Streamlit 启动命令。
- `tests/test_app_qa_workbench.py`
- `tests/test_project_identity.py`

验证命令：

```powershell
python -m unittest tests.test_app_qa_workbench tests.test_project_identity -v
python -m compileall -q clothing_assistant tests
```

通过标准：

- 测试通过。
- `streamlit run clothing_assistant/ui/app_qa.py` 是新的推荐命令。
- 旧入口 wrapper 在一个迁移窗口内保留。

### Phase 4: Infrastructure 迁移

目标：把文件系统、向量库、聊天历史这类外部交互代码移入 `infrastructure/`。

预计改动：

- 移动 `knowledge_base.py` 到 `infrastructure/knowledge_base.py`。
- 移动 `vector_stores.py` 到 `infrastructure/vector_store.py`。
- 移动 `file_history_store.py` 到 `infrastructure/file_history_store.py`。
- 保留短期兼容 wrapper：
  - `clothing_assistant/knowledge_base.py`
  - `clothing_assistant/vector_stores.py`
  - `clothing_assistant/file_history_store.py`
- 更新 `tools/rag_tool.py`、`ui/app_file_uploader.py`、`ui/app_qa.py` 的导入路径。

验证命令：

```powershell
python -m unittest tests.test_agent_pipeline tests.test_app_qa_workbench -v
python -m compileall -q clothing_assistant tests
```

通过标准：

- RAG 检索工具仍能从向量库读取 chunk。
- 上传页仍能读取知识文件、切块并重建本地向量库。
- 本地聊天历史读写行为不变。

### Phase 5: Domain 迁移

目标：让尺码匹配成为更纯的业务规则模块。

预计改动：

- 新建 `domain/size_matching.py`。
- 将纯函数迁入 domain：
  - `extract_user_measurements`
  - `has_complete_measurements`
  - `parse_size_rule_line`
  - `value_in_range`
  - `distance_to_range`
  - `match_size_rule`
- 将文件读取和缓存保留在 infrastructure 或适配层。
- 保留 `clothing_assistant/size_matcher.py` wrapper，提供当前外部调用仍需要的 `match_size_rule(user_query)`。

迁移后的边界：

```text
infrastructure loads size rule text
-> domain parses and matches rules
-> tools/size_tool.py formats Agent tool result
```

验证命令：

```powershell
python -m unittest tests.test_agent_mvp tests.test_agent_pipeline tests.test_langgraph_production_nodes -v
python -m compileall -q clothing_assistant tests
```

通过标准：

- 尺码推荐、缺少身高体重、宽松追问、measurement conflict 行为不变。
- `domain/size_matching.py` 不导入 `clothing_assistant.config_data`。

### Phase 6: Application 服务抽取

目标：把旧 pipeline 中被 LangGraph 复用的回答构造能力抽出来，减少 `agent_executor.py` 与 LangGraph 节点之间的缠绕。

预计改动：

- 新建 `application/answer_service.py`：
  - `build_final_prompt`
  - `default_answer_generator`
  - `build_direct_answer`
  - `build_response_from_state`
- 新建 `infrastructure/llm_client.py`：
  - `get_chat_model`
- 让 `agent/agent_executor.py` 和 `agent/nodes.py` 共同依赖 `application/answer_service.py`。
- 让旧 `rag.py` 不再作为 Agent 公共依赖入口；保留 legacy 生成能力直到后续单独清理。

验证命令：

```powershell
python -m unittest tests.test_agent_pipeline tests.test_langgraph_shadow tests.test_langgraph_production_nodes -v
python -m compileall -q clothing_assistant tests
```

通过标准：

- LangGraph 主线和旧 pipeline 返回结构不变。
- `/chat`、`/chat/pipeline`、`/chat/langgraph` 行为不变。

## 7. 兼容策略

迁移期间优先使用 wrapper，而不是一次性改所有调用方。

wrapper 原则：

- wrapper 只能 re-export 新模块中的函数或调用 `main()`。
- wrapper 不新增业务逻辑。
- wrapper 文件顶部注释标明迁移目标和预计删除条件。
- 删除 wrapper 必须单独开后续清理任务，并先更新 README、docs 和测试。

## 8. 测试策略

每个阶段至少运行该阶段相关测试和编译检查。

完整回归命令：

```powershell
python -m unittest discover -v
python -m compileall -q clothing_assistant tests
```

重点测试范围：

- `tests/test_project_identity.py`：包名、README、LangGraph 配置。
- `tests/test_api.py`：FastAPI 契约。
- `tests/test_app_qa_workbench.py`：Streamlit 工作台辅助函数。
- `tests/test_agent_pipeline.py`：旧 pipeline。
- `tests/test_langgraph_production_nodes.py`：LangGraph 生产节点。
- `tests/test_langgraph_shadow.py`：LangGraph 与旧 pipeline 对照。
- `tests/test_product_catalog.py`：结构化商品查询。

## 9. 风险和回滚

主要风险：

- 文档和代码包名不一致，导致启动命令错误。
- 运行时文件从 Git 移除后，开发者误以为数据丢失。
- UI 文件移动后，Streamlit 启动路径和测试导入路径不同步。
- Domain 抽取过早，导致尺码匹配行为发生细微变化。
- 旧 pipeline 与 LangGraph 共用函数迁移时引入循环依赖。

回滚策略：

- 每个 phase 独立提交。
- 如果某个 phase 出现问题，只回滚该 phase。
- Phase 3 到 Phase 6 均保留 wrapper，降低回滚成本。
- 不在同一提交里同时移动文件、改业务逻辑和改测试断言。

## 10. 批准门槛

开发前需要确认以下事项：

- 是否同意按 Phase 1 到 Phase 6 顺序执行。
- 是否同意短期保留 wrapper，后续再单独删除。
- 是否同意 Phase 2 先只清理 Git 跟踪和 `.gitignore`，暂不改变运行时目录默认位置。
- 是否同意 `api/` 保持顶层包，不强制改成 `interfaces/api/`。

在这些事项确认前，不进行代码迁移。
