# API Reference

本节由 MkDocs 和 mkdocstrings 从 Python Docstrings 生成。第一版只列出生产主线和外部集成最需要阅读的模块，避免把迁移期实验模块误标成正式 API。

当前入口：

```text
docs/api/agent.md
docs/api/tools.md
docs/api/http.md
```

生成命令：

```powershell
mkdocs build --strict
mkdocs serve
```

如果某个模块生成结果不可读，优先修正模块、类、公共函数的 Docstring，而不是在文档页里手工补长篇说明。
