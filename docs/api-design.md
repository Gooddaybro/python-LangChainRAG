# FastAPI 接口设计

本文档定义当前项目的后端接口契约。生产环境中，只有 Java 后端可以调用
FastAPI；前端、App 和小程序必须调用 Java，不能直接调用 Python。Streamlit 只作为
本地调试台、演示页和学习 LangGraph trace 的辅助入口。

## 1. API 目标

`AI Clothing Shopping Assistant System` 面向服装电商导购场景，对外提供一个稳定的 HTTP JSON 接口：

```text
前端 / App / 小程序
-> Java 后端（用户、会话与商业事实所有者）
-> FastAPI /chat（Java internal call）
-> LangGraph 工作流
-> 结构化查询或 RAG
-> 答案校验
-> JSON 响应
```

Java 生产内部调用入口是：

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

### 2.1 本地 PostgreSQL checkpoint

从工作区根目录启动本地依赖；该命令会启动专用的 LangGraph PostgreSQL，Java
业务代码不访问该数据库：

```bash
sh scripts/start-local-deps.sh
cd AI-Clothing-Shopping-Assistant-System
# APP_INTERNAL_API_TOKEN must already be loaded from a private secret store.
AI_RUNTIME_ENV=production \
LANGGRAPH_CHECKPOINTER_BACKEND=postgres \
LANGGRAPH_CHECKPOINTER_DSN='postgresql://...' \
.venv/bin/python -m uvicorn clothing_assistant.api.app:app
```

`LANGGRAPH_CHECKPOINTER_DSN` 必须只在本地 `.env` 或 shell secret storage 中提供，
不能提交真实密码。PostgreSQL checkpoint tables are LangGraph runtime metadata only.
Java/MySQL still owns conversation messages, user identity, product facts, and transaction
state. Request payload channels are untracked and must not appear in durable checkpoints.
The checkpointer tables are created by `PostgresSaver.setup()` on Python startup.

## 3. 接口列表

| 方法 | 路径 | 用途 | 是否生产使用 |
| --- | --- | --- | --- |
| `GET` | `/health` | 健康检查 | 是 |
| `POST` | `/chat` | LangGraph 主线入口 | 是（仅 Java 内部调用） |
| `POST` | `/chat/stream` | LangGraph 真实 SSE 流式入口 | 是（仅 Java 内部调用） |
| `POST` | `/chat/langgraph` | LangGraph 兼容入口 | 过渡兼容（仅 Java 内部调用） |
| `POST` | `/chat/pipeline` | 旧手写 pipeline 对照 | 否（仅 Java 内部调用） |

生产系统由 Java 调用 `/chat`；前端、App 和小程序不得直接调用 Python。
`/chat/pipeline` 只用于迁移期对照、回归检查和学习。

## 4. 请求结构

Endpoint:

```text
POST /chat
Content-Type: application/json
X-Internal-Token: <shared Java/Python internal token>
```

`X-Internal-Token` 是唯一接受的 Python internal authentication header。认证在
`AI_RUNTIME_ENV=production` 或配置了 `APP_INTERNAL_API_TOKEN` 时启用；生产启动时
该环境变量不能为空。不要记录、回显或在客户端代码中硬编码该 token。

### 4.1 请求体大小边界

Python 对 `/chat`、`/chat/stream`、`/chat/pipeline` 和 `/chat/langgraph` 的声明
`Content-Length` 设置上限。`MAX_CHAT_REQUEST_BYTES` 默认值为 `262144`（256 KiB），
且配置值不能小于 `1024`。超过上限时，Python 在执行认证、验证和聊天处理前返回固定
的 `413` 安全错误；不会回显请求体或 `Content-Length` 值。缺失或格式错误的
`Content-Length` 按普通请求继续处理。

该检查仅拒绝过大的**声明**请求体，不负责用户级或分布式限流。Java/网关继续拥有用户
身份、授权及用户级限流的实现和配置。

Request body:

```json
{
  "request_id": "req-api-001",
  "session_id": "session-api-001",
  "thread_id": "thread-api-001",
  "query": "基础款纯棉T恤黑色L码有货吗？",
  "chat_history": [],
  "user_context": {
    "height_cm": 175,
    "weight_kg": 70,
    "preferred_colors": ["黑色"]
  },
  "candidates": [
    {
      "spu_id": 1001,
      "sku_id": 2001,
      "sku_code": "TS-BASIC-001-BLACK-L",
      "name": "基础款纯棉T恤",
      "color": "黑色",
      "size": "L",
      "sale_price": 99,
      "stock_status": "in_stock",
      "available_stock": 8
    }
  ],
  "demand_intent": {
    "version": "demand-intent-v1",
    "source": "java-rule",
    "rawQuery": "基础款纯棉T恤黑色L码有货吗？",
    "category": "T恤",
    "scene": [],
    "style": [],
    "hardFilters": ["color=黑色", "size=L"],
    "softPreferences": []
  },
  "debug": false
}
```

字段说明：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `request_id` | 字符串 | 是 | 无 | Java 生成的、有界请求 ID；正常响应和安全错误响应可用于关联本次调用。 |
| `session_id` | 字符串 | 是 | 无 | Java 会话 ID。 |
| `thread_id` | 字符串/null | 否 | `session_id` | 可选的 LangGraph 线程 ID；为空时 Python 使用 `session_id`。 |
| `query` | 字符串 | 是 | 无 | 用户问题。不能为空或纯空白。 |
| `chat_history` | 数组 | 否 | `[]` | 显式传入的历史对话。当前仍用于追问解析。 |
| `user_context` | 对象 | 否 | `{}` | Java 提供的只读用户画像上下文。 |
| `candidates` | 数组 | 否 | `[]` | Java 为本轮过滤出的 SKU 候选；生产价格、库存、SKU、颜色和尺码事实只来自此列表。 |
| `demand_intent` | 对象/null | 否 | `null` | Java 统一解析出的需求意图。 |
| `debug` | 布尔值 | 否 | `false` | 是否请求内部 debug 信息；仅当本地服务启用 `DEBUG_RESPONSE_ENABLED=true` 时才会返回。 |

Production defaults to `DEBUG_RESPONSE_ENABLED=false`. Debug payloads are returned
only when **both** `debug=true` and `DEBUG_RESPONSE_ENABLED=true`; `debug=true` is an
internal local-diagnostics request, not a client entitlement. Validation logs record
only a safe request id, method, path, and sanitized field errors.

`chat_history` item 当前推荐结构：

```json
{
  "user_query": "我身高178，体重65kg，想买T恤",
  "assistant_answer": "建议选择 L 码。"
}
```

## 5. 响应结构

### 5.1 普通响应

当 debug payload 未同时满足 `debug=true` 和
`DEBUG_RESPONSE_ENABLED=true` 时，接口返回 v1 的用户可见响应：

```json
{
  "request_id": "req-api-001",
  "answer": "基础款纯棉T恤黑色 L 码有货，当前库存 8 件。",
  "intent": "inventory_check",
  "product_refs": [],
  "suggested_actions": []
}
```

| 字段 | 说明 |
| --- | --- |
| `request_id` | 回传本次请求的 `request_id`。 |
| `answer` | 用户可见的回答。 |
| `intent` | Python 工作流识别的本次意图。 |
| `product_refs` | 只引用本次 Java `candidates` 中的商品；无推荐时为 `[]`。 |
| `suggested_actions` | Java 或前端可执行的建议动作；无动作时为 `[]`。 |

生产环境默认应使用这个模式，避免暴露内部 trace、检索资料和业务数据细节。

### 5.2 调试响应

仅当请求为 `debug=true` 且本地服务启用 `DEBUG_RESPONSE_ENABLED=true` 时，
接口才在同一个 v1 响应中附加 `debug`。以下示例假设本地已启用该设置：

```json
{
  "request_id": "req-api-001",
  "answer": "基础款纯棉T恤黑色 L 码有货，当前库存 8 件。",
  "intent": "inventory_check",
  "product_refs": [],
  "suggested_actions": [],
  "debug": {
    "user_query": "基础款纯棉T恤黑色L码有货吗？",
    "thread_id": "thread-api-001",
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

### 5.3 真实 SSE 响应

`POST /chat/stream` 使用与 `/chat` 相同的 LangGraph 路由、工具、validator、
`product_refs` 和事实边界。模型生成路径直接消费 Kimi provider fragment；不再等待
完整回答后人为切块。Python 保留 `STREAM_SAFETY_TAIL_CHARS` 个字符作为安全尾部，
并在公开文本前执行与 `answer_validator` 相同的纯 RAG 交易事实检查。

正常事件顺序保持 v1 契约：

```text
token* -> done
```

`done.answer` 必须等于所有 `token.content` 的精确拼接结果。结构化查询、Java 候选
推荐、尺码规则、直接回答和 fallback 是确定性路径，可能只产生一个 `token` 事件。

模型 timeout、429、连接错误或 5xx 只允许在尚未公开任何文本时进行有界重试。
公开输出开始后不再重试，失败时以安全 `error` 结束且不发送 `done`。客户端断连后，
Python 关闭 provider iterator、停止后续节点和重试，并且不再发送任何事件。

Phase 2 运行参数：

| 环境变量 | 默认值 | 约束 |
| --- | ---: | --- |
| `LLM_TIMEOUT_SECONDS` | `30` | 必须大于 0 |
| `LLM_MAX_RETRIES` | `2` | `0..3` |
| `LLM_MAX_CONCURRENCY` | `8` | 至少 1；仅为 Python 进程内模型并发保护 |
| `RAG_TIMEOUT_SECONDS` | `20` | 必须大于 0 |
| `STREAM_SAFETY_TAIL_CHARS` | `64` | 至少 32 |

## 6. 行为契约

### 6.1 精确事实

生产环境中的库存、价格、SKU、颜色和尺码事实必须来自 Java 请求的
`candidates`，不是 `product_catalog.json`：

```text
Java candidates -> structured_lookup
```

Java 应在调用 `/chat` 前构建候选 SKU。一个精确库存问题的 v1 请求示例：

```json
{
  "request_id": "req-exact-001",
  "session_id": "session-exact-001",
  "query": "基础款纯棉T恤黑色L码有货吗？",
  "chat_history": [],
  "user_context": {},
  "candidates": [
    {
      "spu_id": 1001,
      "sku_id": 2001,
      "sku_code": "TS-BASIC-001-BLACK-L",
      "name": "基础款纯棉T恤",
      "color": "黑色",
      "size": "L",
      "sale_price": 99,
      "stock_status": "in_stock",
      "available_stock": 8
    }
  ],
  "debug": false
}
```

这些问题通过 `structured_lookup` 处理，不能通过 RAG 或大模型编造。
若 Java 传入空 `candidates`，价格或库存问题以
`missing_authoritative_candidates` 停止：不会选择工具、不会断言价格或库存，
也不会返回 `product_refs`。本地
`clothing_assistant/data/product_catalog.json` 仅可在显式
`allow_demo_catalog=True` 的 demo/test 路径使用，不能补全生产事实。

### 6.2 语义知识

颜色搭配、洗涤养护、风格场景、季节适配属于解释性知识，应该走：

```text
rag_retriever -> retrieval_grader
  -> good -> answer_generator -> answer_validator
  -> weak/empty -> fallback_answer
```

示例：

```json
{
  "request_id": "req-semantic-001",
  "session_id": "session-semantic-001",
  "query": "日常通勤推荐什么颜色？",
  "candidates": [],
  "debug": false
}
```

如果本地调试同时满足 `debug=true` 和 `DEBUG_RESPONSE_ENABLED=true`，debug 中的预期路由为：

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
  "request_id": "req-missing-001",
  "session_id": "session-missing-001",
  "query": "黑色M码有货吗？",
  "candidates": [],
  "debug": false
}
```

如果本地调试同时满足 `debug=true` 和 `DEBUG_RESPONSE_ENABLED=true`，缺少商品名时的预期状态为：

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
  ],
  "body": {
    "request_id": "req-api-001"
  }
}
```

`detail` 仅包含已清理的字段位置、错误类型和消息，`body` 仅包含安全的
`request_id`，或在缺失/无效时为 `null`；不会回显原始请求值。

### 7.2 内部错误

未捕获异常会返回：

```json
{
  "error": "internal_server_error",
  "request_id": "req-...",
  "message": "AI service failed to process the request."
}
```

该响应不暴露异常文本、堆栈、prompt 或内部路径；安全的 `request_id` 无法取得时为 `null`。

### 7.3 请求体过大

当受保护聊天路径的声明 `Content-Length` 超过 `MAX_CHAT_REQUEST_BYTES` 时，返回：

```json
{
  "error": "request_too_large",
  "message": "python assistant request exceeds the configured size limit"
}
```

该 `413` 响应不改变 v1 正常 JSON 或 SSE 的字段；也不包含原始请求体、请求头值或
用户级限流状态。

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
    request_id = "req-powershell-001"
    session_id = "session-powershell-001"
    query = "基础款纯棉T恤黑色L码有货吗？"
    chat_history = @()
    user_context = @{}
    candidates = @(
      @{
        spu_id = 1001
        sku_id = 2001
        sku_code = "TS-BASIC-001-BLACK-L"
        name = "基础款纯棉T恤"
        color = "黑色"
        size = "L"
        sale_price = 99
        stock_status = "in_stock"
        available_stock = 8
      }
    )
    debug = $false
  } | ConvertTo-Json -Depth 10)
```

### 8.3 Python 测试

运行：

```powershell
python -m unittest tests.test_api -v
python -m unittest tests.test_langgraph_production_nodes -v
python -m unittest discover -v
```

## 9. Java 内部调用示例

Java 服务使用受控配置中的 `app.internal-api.token` 调用 Python。前端、App 和小程序
不能使用这个接口直接请求 Python。下面是 Java 11+ `HttpClient` 示例：

```java
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

public class ClothingAssistantClient {
    public static void main(String[] args) throws Exception {
        // Java 从商品服务构建当前请求可用的候选 SKU；Python 不读取本地目录补全事实。
        String body = """
            {
              "request_id": "req-java-001",
              "session_id": "session-java-001",
              "thread_id": "thread-java-001",
              "query": "基础款纯棉T恤黑色L码有货吗？",
              "chat_history": [],
              "user_context": {},
              "candidates": [
                {
                  "spu_id": 1001,
                  "sku_id": 2001,
                  "sku_code": "TS-BASIC-001-BLACK-L",
                  "name": "基础款纯棉T恤",
                  "color": "黑色",
                  "size": "L",
                  "sale_price": 99,
                  "stock_status": "in_stock",
                  "available_stock": 8
                }
              ],
              "debug": false
            }
            """;

        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create("http://127.0.0.1:8000/chat"))
            .header("Content-Type", "application/json; charset=utf-8")
            .header("X-Internal-Token", internalApiToken)
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
- Development and tests use an in-memory checkpointer; production requires the
  dedicated PostgreSQL checkpointer configuration described above.
- Debug payloads are returned only when both `debug=true` and `DEBUG_RESPONSE_ENABLED=true`.
- Java `candidates` are the production source for price, inventory, SKU, color, and size facts.
- `product_catalog.json` is only an explicit `allow_demo_catalog=True` demo/test fixture.
- `/chat/stream` uses model-time provider fragments with a safety tail and the same
  deterministic fact validator as `/chat`.
- Model retries are bounded and never occur after public output begins; recoverable RAG
  failures become classified empty evidence and use the existing safe fallback.

生产部署前：

- Set the same non-empty `APP_INTERNAL_API_TOKEN` secret for Python and Java's
  `app.internal-api.token`; Python rejects missing or invalid internal tokens.
- Add request id and access logs.
- Decide whether `thread_id` should fully own conversation memory.
- Preserve the safe `500` response shape without exception text.
- Java/gateway owns user-level distributed rate limiting; Python only rejects oversized
  declared chat request bodies using `MAX_CHAT_REQUEST_BYTES`.
- Add Docker/deployment instructions.

## 11. 当前限制

- This is not yet a multi-tenant API.
- Python chat endpoints require `X-Internal-Token` whenever production mode or
  `APP_INTERNAL_API_TOKEN` enables internal authentication.
- Production PostgreSQL checkpoint tables contain only LangGraph runtime metadata,
  not Java-owned conversation or commerce state.
- `chat_history` still needs to be provided for reliable follow-up behavior.
- Debug payloads require both `debug=true` and `DEBUG_RESPONSE_ENABLED=true` and are intended for development only.
- `product_catalog.json` is an explicit `allow_demo_catalog=True` demo/test fixture; Java `candidates` remain the production commerce fact source.
