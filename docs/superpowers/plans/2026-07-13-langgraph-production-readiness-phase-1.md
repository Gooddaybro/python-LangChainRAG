# LangGraph Production Readiness Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the AI service safe to run as an internal production service: durable LangGraph checkpoint infrastructure, isolated PostgreSQL runtime configuration, Java-to-Python internal authentication, and bounded chat-request input.

**Architecture:** PostgreSQL is a dedicated LangGraph state dependency, separate from the Java/MySQL commerce database. Java continues to own users, messages, commerce facts and user-facing authorization. Python accepts `POST /chat` and `POST /chat/stream` only from the Java service using the existing shared `X-Internal-Token`; direct local development remains explicitly configurable. The checkpointer is selected through a lifecycle-managed factory so unit tests use memory and production uses `PostgresSaver` with a pooled connection.

**Tech Stack:** Python 3.11, FastAPI, LangGraph 1.1, `langgraph-checkpoint-postgres`, psycopg 3, PostgreSQL 16, Docker Compose, Java 21 `HttpClient`, JUnit, Python `unittest`.

## Chosen Deployment Decisions

- Create a dedicated PostgreSQL 16 service named `langgraph-postgres`; it owns only LangGraph checkpoint tables and is not accessed by Java business code.
- Local host port is `5433`; database/user names are both `langgraph`.
- Production mode uses `LANGGRAPH_CHECKPOINTER_BACKEND=postgres` and requires `LANGGRAPH_CHECKPOINTER_DSN`; development/test mode defaults to `memory`.
- Java-to-Python service authentication uses the existing shared `APP_INTERNAL_API_TOKEN` value in the `X-Internal-Token` header. Python production mode fails startup when the token is absent.
- Java keeps its existing user rate limiting. Python adds a request-content-length guard; global multi-instance rate limiting remains Java/gateway responsibility.

## Global Constraints

- Java remains the sole owner of users, sessions, products, prices, inventory, orders, payments, persisted messages, and frontend authorization.
- PostgreSQL is only for LangGraph runtime checkpoints; it must not become a source of commerce facts or user-profile truth.
- Python `candidates`, `user_context`, `chat_history`, raw query, full prompt, raw tool output, and trace events are request-scoped and must not be stored in a durable checkpoint.
- A production request with no Java candidates must keep the Phase 0 `missing_authoritative_candidates` behavior.
- Do not add, remove, or rename any Java-Python v1 JSON fields or SSE event fields.
- `X-Internal-Token` is an HTTP header, not a v1 JSON field. Never log its value or return it to a caller.
- Production `/chat`, `/chat/stream`, `/chat/pipeline`, and `/chat/langgraph` require internal authentication; `/health` and `/health/rag` remain unprotected for container probes.
- A rejected token returns `401` with `{"error":"internal_auth_required","message":"python assistant internal authentication failed"}`; a request that exceeds the byte limit returns `413` with `{"error":"request_too_large","message":"python assistant request exceeds the configured size limit"}`. Neither response contains debug data or body content.
- Tests must not require a live PostgreSQL server, external model, embedding provider, Java server, or secret.
- The repository has no initial Git commit. Do not stage, commit, reset, clean, or modify unrelated untracked files. Use task reports and direct task-scoped review instead of Git diff packages.

---

## File Structure

| File | Responsibility after Phase 1 |
| --- | --- |
| `clothing_assistant/infrastructure/checkpointer.py` | Builds and closes memory or PostgreSQL LangGraph checkpointer runtimes without exposing connection details to graph nodes. |
| `clothing_assistant/config_data.py` | Parses runtime environment, checkpointer, request-size, and internal-token settings with fail-closed production validation. |
| `clothing_assistant/agent/state.py` | Marks request-sensitive graph channels as untracked so durable checkpoint records omit them. |
| `clothing_assistant/agent/langgraph_executor.py` | Obtains a lifecycle-managed runtime saver for normal requests; retains explicit test injection and local cached graph behavior. |
| `clothing_assistant/api/app.py` | Starts/closes the runtime saver, requires the internal header on chat routes, and enforces chat request byte limits. |
| `requirements.txt` | Pins PostgreSQL checkpointer runtime dependencies. |
| `docker-compose.yml`, `.env.example` | Supplies the dedicated local PostgreSQL service and non-secret connection defaults. |
| `RestPythonAssistantClient.java` | Sends the Java internal token on synchronous and SSE Python calls. |
| `RestPythonAssistantClientTests.java` | Proves both Java HTTP paths send the header but never expose the token in JSON. |
| `docs/data-boundary.md`, `docs/api-design.md` | Documents state ownership, internal header requirements, limits, and local startup. |

### Task 1: Add a privacy-preserving, lifecycle-managed checkpointer runtime

**Files:**
- Create: `clothing_assistant/infrastructure/checkpointer.py`
- Modify: `clothing_assistant/config_data.py`
- Modify: `clothing_assistant/agent/state.py`
- Modify: `clothing_assistant/agent/langgraph_executor.py`
- Modify: `tests/test_langgraph_shadow.py`
- Create: `tests/test_checkpointer.py`
- Test: `tests/test_checkpointer.py`, `tests/test_langgraph_shadow.py`

**Interfaces:**
- Produces: `CheckpointerRuntime(saver: Any, close: Callable[[], None])`.
- Produces: `create_checkpointer_runtime(backend: str, dsn: str | None, pool_factory=None, saver_factory=None) -> CheckpointerRuntime`.
- Produces: `get_runtime_checkpointer() -> Any`, `initialize_runtime_checkpointer() -> Any`, and `close_runtime_checkpointer() -> None` in `langgraph_executor.py`.
- Produces: `get_runtime_environment() -> str`, `get_checkpointer_backend() -> str`, and `get_checkpointer_dsn() -> str | None` in `config_data.py`.
- Consumes: `memory` backend without optional PostgreSQL imports; `postgres` backend requires a non-empty DSN and uses `ConnectionPool(conninfo=dsn, min_size=1, max_size=5, kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row})` and `PostgresSaver(pool)` followed by `setup()`.

- [ ] **Step 1: Add failing factory and privacy regressions**

Create `tests/test_checkpointer.py` with injected fakes:

```python
class FakePool:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.closed = False

    def close(self):
        self.closed = True


class FakeSaver:
    def __init__(self, pool):
        self.pool = pool
        self.setup_called = False

    def setup(self):
        self.setup_called = True


def test_postgres_runtime_sets_up_and_closes_pool(self):
    runtime = create_checkpointer_runtime(
        "postgres",
        "postgresql://langgraph:secret@localhost:5432/langgraph",
        pool_factory=FakePool,
        saver_factory=FakeSaver,
    )
    self.assertTrue(runtime.saver.setup_called)
    self.assertEqual(runtime.saver.pool.kwargs["conninfo"], "postgresql://langgraph:secret@localhost:5432/langgraph")
    runtime.close()
    self.assertTrue(runtime.saver.pool.closed)

def test_postgres_runtime_rejects_missing_dsn(self):
    with self.assertRaisesRegex(RuntimeError, "LANGGRAPH_CHECKPOINTER_DSN"):
        create_checkpointer_runtime("postgres", None)
```

Add a graph regression in `tests/test_langgraph_shadow.py` using an injected `InMemorySaver`:

```python
def test_checkpoint_does_not_persist_request_sensitive_channels(self):
    saver = InMemorySaver()
    result = run_langgraph_agent(
        "推荐一件外套",
        chat_history=[{"user_query": "secret history", "assistant_answer": "secret answer"}],
        user_context={"user_id": 7, "preferred_colors": ["secret-color"]},
        candidates=[{"spu_id": 1, "sku_id": 2, "name": "secret candidate"}],
        thread_id="checkpoint-privacy",
        checkpointer=saver,
        tool_registry=build_fake_registry(),
        answer_generator=fake_answer_generator,
    )
    serialized = repr(list(saver.get_state_history({"configurable": {"thread_id": "checkpoint-privacy"}})))
    self.assertNotIn("secret history", serialized)
    self.assertNotIn("secret-color", serialized)
    self.assertNotIn("secret candidate", serialized)
    self.assertEqual(result["debug"]["thread_id"], "checkpoint-privacy")
```

- [ ] **Step 2: Run the tests and observe RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_checkpointer -v
.venv/bin/python -m unittest \
  tests.test_langgraph_shadow.LangGraphShadowTests.test_checkpoint_does_not_persist_request_sensitive_channels -v
```

Expected: imports/functions do not exist, and the privacy regression fails because current checkpoint records contain request state.

- [ ] **Step 3: Implement the pure checkpointer factory and fail-closed config**

In `config_data.py`, add the constants and parsers below. Do not parse or print a DSN anywhere else:

```python
RUNTIME_ENVIRONMENT_ENV = "AI_RUNTIME_ENV"
CHECKPOINTER_BACKEND_ENV = "LANGGRAPH_CHECKPOINTER_BACKEND"
CHECKPOINTER_DSN_ENV = "LANGGRAPH_CHECKPOINTER_DSN"

def get_runtime_environment() -> str:
    return os.getenv(RUNTIME_ENVIRONMENT_ENV, "development").strip().lower()

def get_checkpointer_backend() -> str:
    backend = os.getenv(CHECKPOINTER_BACKEND_ENV, "").strip().lower()
    if not backend:
        return "postgres" if get_runtime_environment() == "production" else "memory"
    if backend not in {"memory", "postgres"}:
        raise RuntimeError("LANGGRAPH_CHECKPOINTER_BACKEND must be memory or postgres")
    if get_runtime_environment() == "production" and backend != "postgres":
        raise RuntimeError("production requires LANGGRAPH_CHECKPOINTER_BACKEND=postgres")
    return backend

def get_checkpointer_dsn() -> str | None:
    dsn = os.getenv(CHECKPOINTER_DSN_ENV, "").strip()
    if get_checkpointer_backend() == "postgres" and not dsn:
        raise RuntimeError("LANGGRAPH_CHECKPOINTER_DSN is required for postgres")
    return dsn or None
```

Create `checkpointer.py` with a `CheckpointerRuntime` dataclass, a `memory` branch returning `InMemorySaver` and a no-op `close`, and the injected PostgreSQL branch described in the Interfaces block. Import `PostgresSaver`, `ConnectionPool`, and `dict_row` only inside the `postgres` branch. `close` must close the pool exactly once.

- [ ] **Step 4: Mark sensitive graph channels untracked and add runtime injection**

Use `langgraph.channels.UntrackedValue` in `AgentState` for every field that can carry a raw query, message/history text, user context, candidates, demand intent, tool result, draft/final answer, prompt, accepted/rejected chunk, trace event, or evidence summary. Preserve the current in-run reducer behavior for `trace_events` by creating an `UntrackedTraceEvents` channel in `state.py`: it appends node event lists in `update()`, returns `MISSING` from `checkpoint()`, and creates an empty copy from a checkpoint.

`thread_id`, `run_id`, request IDs, counters, routes, validation booleans, fallback kind/reason, and stop reason may be checkpointed only if they contain no user text, product data, prompt, or tool payload. Prefer untracked when uncertain.

In `langgraph_executor.py`:

```python
_RUNTIME_CHECKPOINTER = None

def initialize_runtime_checkpointer():
    global _RUNTIME_CHECKPOINTER
    if _RUNTIME_CHECKPOINTER is None:
        _RUNTIME_CHECKPOINTER = create_checkpointer_runtime(
            get_checkpointer_backend(),
            get_checkpointer_dsn(),
        )
    return _RUNTIME_CHECKPOINTER.saver

def get_runtime_checkpointer():
    return initialize_runtime_checkpointer()

def close_runtime_checkpointer():
    global _RUNTIME_CHECKPOINTER
    if _RUNTIME_CHECKPOINTER is not None:
        _RUNTIME_CHECKPOINTER.close()
        _RUNTIME_CHECKPOINTER = None
```

Add `checkpointer=None` to `run_langgraph_agent`. Normal request-scoped graph construction uses `checkpointer or get_runtime_checkpointer()`. Keep `use_cached_graph=True` using the existing local cached in-memory graph so current workbench tests preserve their explicit behavior. Pass the injected saver directly through the normal request-scoped path.

- [ ] **Step 5: Run focused tests and inspect checkpoint payload**

Run:

```bash
.venv/bin/python -m unittest tests.test_checkpointer tests.test_langgraph_shadow -v
```

Expected: factory tests and privacy regression pass; existing thread/checkpoint tests remain green.

### Task 2: Add the dedicated PostgreSQL local runtime and checkpoint documentation

**Files:**
- Modify: `requirements.txt`
- Modify: `../IntelligentOutfitRecommendationSystem/docker-compose.yml`
- Modify: `../.env.example`
- Modify: `.env.example`
- Modify: `docs/data-boundary.md`
- Modify: `docs/api-design.md`
- Modify: `README.md`
- Modify: `tests/test_reproducible_environment.py`
- Test: `tests/test_reproducible_environment.py`, `tests/test_project_identity.py`

**Interfaces:**
- Produces: local PostgreSQL service `langgraph-postgres` on `${LANGGRAPH_POSTGRES_HOST_PORT:-5433}` with database/user `langgraph` and persistent volume `langgraph_postgres_data`.
- Produces: `LANGGRAPH_CHECKPOINTER_DSN=postgresql://langgraph:${LANGGRAPH_POSTGRES_PASSWORD}@localhost:${LANGGRAPH_POSTGRES_HOST_PORT}/langgraph` as a documented shell/template value; no secret-bearing DSN is committed.
- Produces: requirements `langgraph-checkpoint-postgres>=3.1.0,<4` and `psycopg[binary,pool]>=3.2.0,<4`.

- [ ] **Step 1: Add failing reproducibility assertions**

In `tests/test_reproducible_environment.py`, parse the root compose YAML as text and assert it contains `langgraph-postgres`, `postgres:16`, `${LANGGRAPH_POSTGRES_HOST_PORT:-5433}:5432`, and `langgraph_postgres_data`. Assert root `.env.example` contains the non-secret PostgreSQL host/database/user/password variable names, and Python `.env.example` documents `AI_RUNTIME_ENV`, `LANGGRAPH_CHECKPOINTER_BACKEND`, and `LANGGRAPH_CHECKPOINTER_DSN` without a concrete password.

- [ ] **Step 2: Run the focused test and observe RED**

Run:

```bash
python3 -m unittest tests.test_reproducible_environment -v
```

Expected: failure because the local dependency stack does not yet define PostgreSQL.

- [ ] **Step 3: Add the database service and dependencies**

Add to root compose:

```yaml
  langgraph-postgres:
    image: postgres:16
    container_name: intelligent_outfit_langgraph_postgres
    ports:
      - "${LANGGRAPH_POSTGRES_HOST_PORT:-5433}:5432"
    environment:
      POSTGRES_DB: ${LANGGRAPH_POSTGRES_DATABASE:-langgraph}
      POSTGRES_USER: ${LANGGRAPH_POSTGRES_USERNAME:-langgraph}
      POSTGRES_PASSWORD: ${LANGGRAPH_POSTGRES_PASSWORD:-change-me-locally}
      TZ: Asia/Shanghai
    volumes:
      - langgraph_postgres_data:/var/lib/postgresql/data
```

Add `langgraph_postgres_data:` to volumes. Add matching root environment variable names with non-secret local defaults, and add Python `.env.example` comments explaining that development uses memory by default while a local Docker PostgreSQL run must set `AI_RUNTIME_ENV=production`, `LANGGRAPH_CHECKPOINTER_BACKEND=postgres`, and a locally supplied DSN. Add the two Python dependency ranges exactly as specified above.

- [ ] **Step 4: Document ownership, startup, and lifecycle**

Update data/API/README docs to state:

```text
PostgreSQL checkpoint tables are LangGraph runtime metadata only. Java/MySQL still owns
conversation messages, user identity, product facts, and transaction state. Request
payload channels are untracked and must not appear in durable checkpoints. The
checkpointer tables are created by PostgresSaver.setup() on Python startup.
```

Include local commands:

```bash
sh scripts/start-local-deps.sh
cd AI-Clothing-Shopping-Assistant-System
AI_RUNTIME_ENV=production \
LANGGRAPH_CHECKPOINTER_BACKEND=postgres \
LANGGRAPH_CHECKPOINTER_DSN='postgresql://...' \
.venv/bin/python -m uvicorn clothing_assistant.api.app:app
```

Do not place a real password in the docs or `.env.example`.

- [ ] **Step 5: Run focused checks**

Run:

```bash
python3 -m unittest tests.test_reproducible_environment -v
.venv/bin/python -m unittest tests.test_project_identity tests.test_checkpointer -v
```

Expected: all checks pass without launching Docker or contacting PostgreSQL.

### Task 3: Require Java-to-Python internal authentication on chat routes

**Files:**
- Modify: `clothing_assistant/config_data.py`
- Modify: `clothing_assistant/api/app.py`
- Modify: `tests/test_api.py`
- Modify: `../IntelligentOutfitRecommendationSystem/backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/assistant/client/RestPythonAssistantClient.java`
- Modify: `../IntelligentOutfitRecommendationSystem/backend/src/test/java/com/recommendation/intelligentoutfitrecommendationsystem/assistant/RestPythonAssistantClientTests.java`
- Modify: `../.env.example`
- Modify: `docs/api-design.md`
- Test: `tests/test_api.py`, Java `RestPythonAssistantClientTests`

**Interfaces:**
- Produces: `X-Internal-Token` as the only accepted internal request header.
- Produces: `is_internal_auth_required() -> bool`, true when `AI_RUNTIME_ENV=production` or `APP_INTERNAL_API_TOKEN` is configured.
- Produces: production startup validation that rejects a missing internal token.
- Consumes: Java property `app.internal-api.token` unchanged.

- [ ] **Step 1: Add failing Python and Java header tests**

In `tests/test_api.py`, patch production config/token values and assert:

```python
response = self.client.post("/chat", json=valid_request)
self.assertEqual(response.status_code, 401)
self.assertEqual(response.json(), {
    "error": "internal_auth_required",
    "message": "python assistant internal authentication failed",
})

response = self.client.post(
    "/chat",
    headers={"X-Internal-Token": "test-internal-token"},
    json=valid_request,
)
self.assertEqual(response.status_code, 200)
```

Repeat the reject case for `/chat/stream`; assert `/health` is still `200` without a header. In Java client tests capture `exchange.getRequestHeaders().getFirst("X-Internal-Token")` on both `/chat` and `/chat/stream`, then assert it equals a constructor-supplied test token.

- [ ] **Step 2: Run focused tests and observe RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_api -v
cd ../IntelligentOutfitRecommendationSystem/backend && sh ./mvnw -q -Dtest=RestPythonAssistantClientTests test
```

Expected: Python accepts missing headers and Java does not send them.

- [ ] **Step 3: Implement constant-time Python validation and lifecycle validation**

Add `get_internal_api_token()` and `is_internal_auth_required()` to `config_data.py`. `get_internal_api_token()` returns the trimmed `APP_INTERNAL_API_TOKEN` or an empty string. Production requires a non-empty token.

In `api/app.py`, use `hmac.compare_digest` in an async dependency:

```python
INTERNAL_TOKEN_HEADER = "X-Internal-Token"

async def require_internal_auth(request: Request):
    if not is_internal_auth_required():
        return
    expected = get_internal_api_token()
    supplied = request.headers.get(INTERNAL_TOKEN_HEADER, "")
    if not expected or not hmac.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "internal_auth_required",
                "message": "python assistant internal authentication failed",
            },
        )
```

Attach `Depends(require_internal_auth)` to all four chat routes, not health routes. Add a FastAPI lifespan that calls `initialize_runtime_checkpointer()` before yield, validates that production has a token, then calls `close_runtime_checkpointer()` after yield. Do not log supplied or expected token values.

- [ ] **Step 4: Send the existing Java token on both client calls**

Add constructor parameter `@Value("${app.internal-api.token}") String internalApiToken`, store it in a field, and add:

```java
.header("X-Internal-Token", internalApiToken)
```

to both `HttpRequest` builders. Update all direct constructor calls in Java tests with `"test-internal-token"`. Keep payload JSON unchanged.

- [ ] **Step 5: Update local templates and run contract checks**

Document the required shared `APP_INTERNAL_API_TOKEN` environment variable in Python `.env.example` without a real value. Update API docs so production clients must call through Java and do not call Python directly. Run:

```bash
.venv/bin/python -m unittest tests.test_api tests.test_shared_contract -v
cd ../IntelligentOutfitRecommendationSystem/backend && sh ./mvnw -q -Dtest=RestPythonAssistantClientTests test
```

Expected: Python and Java tests pass; v1 JSON field tests remain unchanged.

### Task 4: Enforce a bounded chat request body at the Python service edge

**Files:**
- Modify: `clothing_assistant/config_data.py`
- Modify: `clothing_assistant/api/app.py`
- Modify: `tests/test_api.py`
- Modify: `.env.example`
- Modify: `docs/api-design.md`
- Test: `tests/test_api.py`

**Interfaces:**
- Produces: `get_max_chat_request_bytes() -> int`, parsing `MAX_CHAT_REQUEST_BYTES` with default `262144` and rejecting values smaller than `1024`.
- Produces: `413` `request_too_large` response only for `/chat`, `/chat/stream`, `/chat/pipeline`, and `/chat/langgraph` when a declared `Content-Length` exceeds the configured limit.
- Consumes: Java continues to enforce per-user rate limits; Python's byte guard does not attempt distributed user-rate accounting.

- [ ] **Step 1: Add failing request-size tests**

Patch `clothing_assistant.api.app.get_max_chat_request_bytes` to return `64`. Submit a `/chat` request with header `Content-Length: 65` and assert `413` plus exactly:

```json
{
  "error": "request_too_large",
  "message": "python assistant request exceeds the configured size limit"
}
```

Patch `run_langgraph_agent` to raise if called. Add a normal declared-size request below the limit that reaches the mocked executor. Confirm `/health` ignores the header and remains `200`.

- [ ] **Step 2: Run focused tests and observe RED**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_api.ApiTests.test_chat_rejects_declared_request_larger_than_limit \
  tests.test_api.ApiTests.test_chat_allows_declared_request_within_limit -v
```

Expected: current API accepts both requests because no edge byte guard exists.

- [ ] **Step 3: Add the middleware and safe configuration parser**

In `config_data.py`:

```python
def get_max_chat_request_bytes() -> int:
    raw_value = os.getenv("MAX_CHAT_REQUEST_BYTES", "262144").strip()
    try:
        value = int(raw_value)
    except ValueError as error:
        raise RuntimeError("MAX_CHAT_REQUEST_BYTES must be an integer") from error
    if value < 1024:
        raise RuntimeError("MAX_CHAT_REQUEST_BYTES must be at least 1024")
    return value
```

In `app.py`, add HTTP middleware that only inspects chat paths and parses `Content-Length` as a non-negative integer. If it exceeds `get_max_chat_request_bytes()`, return the exact 413 JSON above without calling downstream middleware/handlers. If the header is missing, malformed, or within the limit, continue normally; Java `HttpClient` supplies a content length for ordinary JSON calls. Do not include a request body or header value in the error response/log.

- [ ] **Step 4: Document the boundary and run focused tests**

Document `MAX_CHAT_REQUEST_BYTES=262144` in `.env.example` and the API docs, including that Java/gateway owns user rate limiting while Python only rejects oversized declared bodies. Run:

```bash
.venv/bin/python -m unittest tests.test_api -v
```

Expected: API tests pass; the limit does not change the v1 JSON schema.

## Plan Self-Review

- **Spec coverage:** Task 1 covers checkpointer lifecycle, injected testability, state privacy, and thread isolation. Task 2 provides the dedicated Postgres runtime and reproducible documentation. Task 3 adds the chosen service authentication across Java and Python. Task 4 adds Python's bounded input protection while preserving Java-owned distributed rate limiting.
- **Scope:** No multi-agent behavior, MQ, vector database, long-term Python memory, Java commerce mutation, v1 JSON field change, or real external-service test is introduced.
- **Consistency:** All production checkpointer settings use the `LANGGRAPH_CHECKPOINTER_*` names; both Java HTTP paths use `X-Internal-Token`; all rejected tokens and body limits return the fixed safe payloads.
- **Placeholder scan:** the four tasks include concrete file paths, signatures, test names, expected commands, and fixed error outputs.
