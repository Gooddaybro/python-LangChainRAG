# FastAPI 接口设计

本文档定义当前项目的后端接口契约。生产调用方应优先接入 FastAPI；
Streamlit 只作为本地调试台、演示页和学习 LangGraph trace 的辅助入口。

## 1. API 目标

`AI Clothing Shopping Assistant System` 面向服装电商导购场景，对外提供一个稳定的 HTTP JSON 接口：

```text
Java / 前端 / App / 小程序
-> FastAPI /chat
-> LangGraph 工作流
-> 结构化查询或 RAG
-> 答案校验
-> JSON 响应
```

生产主入口是：

```text
POST /chat
```

兼容和调试入口是：

```text
POST /chat/langgraph
POST /chat/pipeline
```

## 2. 运行端口

端口不由 `clothing_assistant/api/app.py` 决定，而由启动命令决定。

默认启动：

```powershell
uvicorn clothing_assistant.api.app:app --reload
```

默认地址：

```text
http://127.0.0.1:8000
```

如果 `8000` 被占用：

```powershell
uvicorn clothing_assistant.api.app:app --reload --port 8001
```

常用本地入口：

```text
FastAPI 文档页: http://127.0.0.1:8000/docs
OpenAPI JSON: http://127.0.0.1:8000/openapi.json
Streamlit 调试页: http://127.0.0.1:8501
```

查看当前监听端口：

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8000,8001,8501
```

## 3. 接口列表

| 方法 | 路径 | 用途 | 是否生产使用 |
| --- | --- | --- | --- |
| `GET` | `/health` | 健康检查 | 是 |
| `POST` | `/chat` | LangGraph 主线入口 | 是 |
| `POST` | `/chat/langgraph` | LangGraph 兼容入口 | 过渡兼容 |
| `POST` | `/chat/pipeline` | 旧手写 pipeline 对照 | 否 |

生产系统和 Java 调用方应使用 `/chat`。`/chat/pipeline` 只用于迁移期对照、回归检查和学习。

## 4. 请求结构

Endpoint:

```text
POST /chat
Content-Type: application/json
```

Request body:

```json
{
  "query": "基础款纯棉T恤黑色L码有货吗？",
  "chat_history": [],
  "thread_id": "api-test-001",
  "debug": true
}
```

字段说明：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `query` | 字符串 | 是 | 无 | 用户问题。不能为空或纯空白。 |
| `chat_history` | 数组 | 否 | `[]` | 显式传入的历史对话。当前仍用于追问解析。 |
| `thread_id` | 字符串/null | 否 | 自动生成 | LangGraph checkpoint/debug 的会话 id。 |
| `debug` | 布尔值 | 否 | `false` | 是否返回内部 debug 信息。生产默认应为 `false`。 |

`chat_history` item 当前推荐结构：

```json
{
  "user_query": "我身高178，体重65kg，想买T恤",
  "assistant_answer": "建议选择 L 码。"
}
```

## 5. 响应结构

### 5.1 普通响应

当 `debug=false` 时，接口只返回用户可见答案：

```json
{
  "answer": "基础款纯棉T恤黑色 L 码有货，当前库存 8 件。"
}
```

生产环境默认应使用这个模式，避免暴露内部 trace、检索资料和业务数据细节。

### 5.2 调试响应

当 `debug=true` 时，接口返回完整 Agent 结果：

```json
{
  "answer": "基础款纯棉T恤黑色 L 码有货，当前库存 8 件。",
  "debug": {
    "user_query": "基础款纯棉T恤黑色L码有货吗？",
    "thread_id": "api-test-001",
    "run_id": "run-...",
    "intent_result": {
      "intent": "inventory_check",
      "need_history": false,
      "reason": "命中库存、颜色是否有货相关关键词。",
      "query_type": "inventory"
    },
    "selected_tools": ["structured_lookup"],
    "structured_result": {
      "lookup_type": "inventory",
      "matched_product_id": "TSHIRT_BASIC_001",
      "matched_product_name": "基础款纯棉T恤",
      "color": "黑色",
      "size": "L",
      "stock_count": 8,
      "in_stock": true
    },
    "accepted_chunks": [],
    "rejected_chunks": [],
    "validation_result": {
      "grounded": true,
      "reason": "structured facts validated"
    },
    "stop_reason": "final_answer",
    "trace_events": []
  }
}
```

Debug 字段用于开发、测试、eval 和排查，不建议直接暴露给普通用户。

## 6. 行为契约

### 6.1 精确事实

库存、价格、SKU、颜色列表、尺码规则 id 必须来自结构化数据：

```text
clothing_assistant/data/product_catalog.json
```

这些问题应该走：

```text
structured_lookup
```

不能通过 RAG 或大模型编造。

示例：

```json
{
  "query": "基础款纯棉T恤多少钱？",
  "debug": true
}
```

预期：

```json
{
  "selected_tools": ["structured_lookup"],
  "structured_result": {
    "price_cny": 99
  }
}
```

### 6.2 语义知识

颜色搭配、洗涤养护、风格场景、季节适配属于解释性知识，应该走：

```text
rag_retriever -> retrieval_grader -> answer_generator -> answer_validator
```

示例：

```json
{
  "query": "日常通勤推荐什么颜色？",
  "debug": true
}
```

预期：

```json
{
  "selected_tools": ["rag_tool"],
  "accepted_chunks": [
    {
      "file_name": "颜色选择.txt"
    }
  ]
}
```

### 6.3 缺失信息

缺少关键字段时，接口应追问，不应猜测。

示例：

```json
{
  "query": "黑色M码有货吗？",
  "debug": true
}
```

预期：

```json
{
  "selected_tools": [],
  "stop_reason": "missing_info",
  "missing_info_result": {
    "missing_fields": ["product"]
  }
}
```

## 7. 错误契约

### 7.1 参数校验错误

空问题或缺少必填字段会返回 FastAPI/Pydantic 的 `422`：

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "query"],
      "msg": "String should have at least 1 character"
    }
  ]
}
```

### 7.2 内部错误

未捕获异常会返回：

```json
{
  "error": "internal_server_error",
  "detail": "error message"
}
```

生产化后应进一步收敛 `detail`，避免把内部异常暴露给外部调用方。

## 8. API 测试

### 8.1 Swagger 文档页

Open:

```text
http://127.0.0.1:8000/docs
```

使用方式：

```text
Try it out -> fill JSON -> Execute
```

### 8.2 PowerShell

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/chat" `
  -ContentType "application/json; charset=utf-8" `
  -Body (@{
    query = "基础款纯棉T恤黑色L码有货吗？"
    chat_history = @()
    thread_id = "api-test-001"
    debug = $true
  } | ConvertTo-Json -Depth 10)
```

### 8.3 Python 测试

运行：

```powershell
python -m unittest tests.test_api -v
python -m unittest tests.test_langgraph_production_nodes -v
python -m unittest discover -v
```

## 9. Java 调用示例

Java 调用方只需要发送 HTTP POST JSON。下面是 Java 11+ `HttpClient` 示例：

```java
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

public class ClothingAssistantClient {
    public static void main(String[] args) throws Exception {
        String body = """
            {
              "query": "基础款纯棉T恤黑色L码有货吗？",
              "chat_history": [],
              "thread_id": "java-client-001",
              "debug": false
            }
            """;

        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create("http://127.0.0.1:8000/chat"))
            .header("Content-Type", "application/json; charset=utf-8")
            .POST(HttpRequest.BodyPublishers.ofString(body))
            .build();

        HttpResponse<String> response = HttpClient.newHttpClient()
            .send(request, HttpResponse.BodyHandlers.ofString());

        System.out.println(response.statusCode());
        System.out.println(response.body());
    }
}
```

## 10. 生产注意事项

当前状态：

- `/chat` already uses LangGraph main workflow.
- `thread_id` is passed to LangGraph checkpointer/debug config.
- `chat_history` is still explicitly passed by the caller.
- `debug=false` hides internal debug data.
- `product_catalog.json` is the current structured data source.

生产部署前：

- Add authentication or internal gateway protection.
- Add request id and access logs.
- Add timeout and retry policy for model calls.
- Replace local `InMemorySaver` with database checkpointer.
- Decide whether `thread_id` should fully own conversation memory.
- Hide internal exception details in `500` responses.
- Add rate limiting and request size limits.
- Add Docker/deployment instructions.

## 11. 当前限制

- This is not yet a multi-tenant API.
- There is no authentication.
- There is no production database checkpointer.
- `chat_history` still needs to be provided for reliable follow-up behavior.
- `debug=true` is intended for development only.
- Product catalog is JSON; SQLite/Postgres can replace it later without changing the API contract.
