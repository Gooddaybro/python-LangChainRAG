# LangGraph Production Readiness Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver safe model-time SSE, cooperative disconnect cancellation, and bounded LLM/RAG failure handling without changing the Java-Python v1 contract.

**Architecture:** Keep one LangGraph business graph and inject a streaming answer generator at its existing answer-generation seam. A request-scoped worker feeds internal token events through a safety buffer while the normal validator remains authoritative; FastAPI only translates accepted internal events into the existing `token`, `done`, and `error` SSE events.

**Tech Stack:** Python 3.11, FastAPI 0.136, LangGraph 1.1, langchain-openai 1.1, httpx 0.28, Python `unittest`.

## Global Constraints

- Follow `docs/superpowers/specs/2026-07-12-langgraph-production-readiness-design.md` and `docs/superpowers/specs/2026-07-14-langgraph-production-readiness-phase-2-design.md`.
- Continue from the current Phase 1 working tree; do not reset, clean, overwrite, or stage unrelated changes.
- Keep one LangGraph business flow and the existing answer validator.
- Keep `/chat`, `/chat/stream`, v1 JSON fields, and SSE `token`/`done`/`error` fields unchanged.
- Never stream a price, inventory, SKU, or availability fact unsupported by current Java candidates.
- Never expose prompts, raw chunks, trace events, credentials, or provider exception text.
- Do not add a new model SDK, queue, broker, WebSocket, multi-agent layer, or distributed rate limiter.
- All runtime behavior changes follow RED-GREEN-REFACTOR; no external service or secret is required by tests.

---

## File Structure

| File | Phase 2 responsibility |
| --- | --- |
| `clothing_assistant/config_data.py` | Parse timeout, retry, concurrency, RAG, and stream-tail settings. |
| `clothing_assistant/infrastructure/llm_client.py` | Classify provider failures and own bounded LLM retry/concurrency. |
| `clothing_assistant/infrastructure/vector_store.py` | Use the configured RAG timeout. |
| `clothing_assistant/tools/rag_tool.py` | Convert recoverable RAG failures into classified empty evidence. |
| `clothing_assistant/api/streaming.py` | Buffer and validate provider fragments and format v1 SSE. |
| `clothing_assistant/agent/langgraph_executor.py` | Run the existing graph with an injected streaming answer generator and emit internal stream events. |
| `clothing_assistant/api/app.py` | Bridge internal events to SSE and close the run on disconnect. |
| `tests/test_llm_client.py` | Prove model timeout/retry/concurrency behavior. |
| `tests/test_rag_tool.py` | Prove recoverable RAG degradation. |
| `tests/test_chat_stream.py` | Prove real timing, safety, cancellation, and v1 output. |
| `.env.example`, `docs/api-design.md`, `README.md` | Document Phase 2 runtime settings and smoke tests. |

### Task 1: Add fail-closed Phase 2 configuration and bounded LLM runtime policy

**Files:**
- Modify: `clothing_assistant/config_data.py`
- Modify: `clothing_assistant/infrastructure/llm_client.py`
- Modify: `tests/test_config_data.py`
- Modify: `tests/test_llm_client.py`

**Interfaces:**
- Produces: `get_llm_timeout_seconds() -> float` default `30`.
- Produces: `get_llm_max_retries() -> int` default `2`, range `0..3`.
- Produces: `get_llm_max_concurrency() -> int` default `8`, minimum `1`.
- Produces: `get_rag_timeout_seconds() -> float` default `20`.
- Produces: `get_stream_safety_tail_chars() -> int` default `64`, minimum `32`.
- Produces: `DependencyError(dependency, reason, retryable)`.
- Produces: `stream_chat_content(messages, *, model_factory=None, stop_requested=None, sleep=None) -> Iterator[str]`.

- [ ] **Step 1: Add failing configuration tests**

Add table-driven assertions for defaults, whitespace normalization, invalid numbers, retry range, positive timeout/concurrency, and minimum safety tail.

- [ ] **Step 2: Run configuration tests and observe RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_config_data -v
```

Expected: imports for the five Phase 2 parsers fail.

- [ ] **Step 3: Implement the minimal parsers**

Use shared private integer/float parsing helpers in `config_data.py`; raise `RuntimeError` naming the invalid environment variable. Do not read these values at import time.

- [ ] **Step 4: Run configuration tests and observe GREEN**

Run the Step 2 command. Expected: all configuration tests pass.

- [ ] **Step 5: Add failing LLM policy tests**

Cover these behaviors with injected model factories and `sleep=lambda _: None`:

```python
def test_stream_chat_content_yields_real_provider_fragments(): ...
def test_stream_chat_content_retries_timeout_before_output(): ...
def test_stream_chat_content_does_not_retry_after_output(): ...
def test_stream_chat_content_does_not_retry_non_retryable_4xx(): ...
def test_stream_chat_content_stops_and_closes_provider_iterator(): ...
def test_chat_model_disables_sdk_retries_and_sets_timeout(): ...
```

Fake chunks expose `.content`; fake failures expose `status_code` or inherit `TimeoutError`/`ConnectionError`.

- [ ] **Step 6: Run LLM policy tests and observe RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_llm_client -v
```

Expected: streaming interfaces and explicit timeout/retry settings do not exist.

- [ ] **Step 7: Implement bounded streaming policy**

Configure `ChatOpenAI(request_timeout=get_llm_timeout_seconds(), max_retries=0)`. Use one process-local `BoundedSemaphore`, classify timeout/connection/429/5xx as retryable, close iterators in `finally`, retry only before a fragment has been yielded, and raise `DependencyError` without embedding the provider message.

- [ ] **Step 8: Run focused tests and observe GREEN**

Run:

```bash
.venv/bin/python -m unittest tests.test_config_data tests.test_llm_client -v
```

Expected: all tests pass without an API key or network.

### Task 2: Make RAG external failures bounded and safely degradable

**Files:**
- Modify: `clothing_assistant/infrastructure/vector_store.py`
- Modify: `clothing_assistant/tools/rag_tool.py`
- Modify: `tests/test_vector_store.py`
- Modify: `tests/test_rag_tool.py`

**Interfaces:**
- Consumes: `get_rag_timeout_seconds()` and `DependencyError`.
- Produces: unchanged `run_rag_tool()` result fields plus internal `rag_meta.degraded_reason` when an external dependency fails.

- [ ] **Step 1: Add failing RAG timeout and classification tests**

Assert `JinaEmbeddings._embed()` passes the configured timeout. Assert timeout, connection, 429, and 5xx failures return zero chunks with one of `timeout`, `connection_error`, `rate_limited`, or `upstream_5xx`; assert an unrelated programming error is not swallowed.

- [ ] **Step 2: Run focused tests and observe RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_vector_store tests.test_rag_tool -v
```

Expected: timeout is still a fixed constant and recoverable failures escape `run_rag_tool()`.

- [ ] **Step 3: Implement the minimal RAG boundary**

Use the configuration parser at the `httpx.post()` call. Translate only known `httpx.TimeoutException`, `httpx.ConnectError`, and `httpx.HTTPStatusError` 429/5xx cases; return the existing empty-evidence shape with a safe reason enum. Keep malformed local data and programming errors visible to tests.

- [ ] **Step 4: Run focused tests and observe GREEN**

Run the Step 2 command. Expected: all vector/RAG tests pass.

### Task 3: Add the safety buffer at the SSE boundary

**Files:**
- Modify: `clothing_assistant/api/streaming.py`
- Modify: `tests/test_chat_stream.py`

**Interfaces:**
- Produces: `UnsafeStreamContent(RuntimeError)`.
- Produces: `SafeTokenBuffer(tail_chars: int, validator: Callable[[str], str | None])`.
- Produces: `push(fragment: str) -> list[str]`, `finish() -> list[str]`, `text`, and `emitted_text`.

- [ ] **Step 1: Add failing buffer tests**

Prove empty chunks are ignored, arbitrary provider boundaries preserve text, the configured tail is withheld, and `库存 8 件` / `售价 99 元` / `SKU ABC 已上架` split across fragments raises before the offending buffered text is released.

- [ ] **Step 2: Run buffer tests and observe RED**

Run the named `ChatStreamHelperTests` buffer tests. Expected: `SafeTokenBuffer` does not exist.

- [ ] **Step 3: Implement the minimal buffer**

Accumulate full text for validation, hold only the configured suffix, and return newly safe text. Reuse `find_forbidden_rag_fact`; do not copy its regexes. `finish()` releases the remaining tail only after its caller has received final validator acceptance.

- [ ] **Step 4: Run helper tests and observe GREEN**

Run:

```bash
.venv/bin/python -m unittest tests.test_chat_stream.ChatStreamHelperTests -v
```

Expected: all SSE helper and buffer tests pass.

### Task 4: Stream through the existing LangGraph and cancel on disconnect

**Files:**
- Modify: `clothing_assistant/application/answer_service.py`
- Modify: `clothing_assistant/agent/langgraph_executor.py`
- Modify: `clothing_assistant/api/app.py`
- Modify: `tests/test_chat_stream.py`
- Modify: `tests/test_langgraph_shadow.py`

**Interfaces:**
- Produces: internal `AgentStreamEvent(kind: str, content: str = "", result: dict | None = None, code: str = "")`.
- Produces: `stream_langgraph_agent(..., stop_requested=None, stream_content=None) -> Iterator[AgentStreamEvent]`.
- Produces: async `generate_chat_stream(chat_request, http_request)`.
- Consumes: the existing `run_langgraph_agent` graph builder, validator, response builder, `SafeTokenBuffer`, and `stream_chat_content`.

- [ ] **Step 1: Add a failing real-timing executor test**

Use a fake provider iterator blocked by a `threading.Event`. Assert the first internal token event is received before the fake iterator is allowed to complete. Do not use elapsed-time sleeps as the assertion.

- [ ] **Step 2: Run the timing test and observe RED**

Run the named test. Expected: `stream_langgraph_agent` does not exist.

- [ ] **Step 3: Implement the internal streaming executor**

Run the existing synchronous graph in one request-scoped daemon thread and communicate via `queue.Queue`. Inject an answer generator that builds the same prompt/messages as `generate_final_answer`, consumes `stream_chat_content`, and emits only buffer-approved text. After graph completion:

- If the accepted final answer starts with all emitted text, emit the remaining accepted suffix and one result event.
- If validation changed an already-public prefix, emit a safe validation error and no result.
- If unsafe text is found before public output, return the draft to the normal validator so its existing retry limit applies.
- If unsafe text is found after public output, stop with a safe validation error.
- In generator `finally`, signal cancellation and join the worker so it cannot outlive the request.

- [ ] **Step 4: Add failing cancellation and consistency tests**

Assert closing the internal iterator closes the fake provider iterator and prevents result/done. Assert deterministic `/chat` and streaming runs return equal accepted answer, intent, `product_refs`, and stop reason. Assert token concatenation equals final answer.

- [ ] **Step 5: Run focused executor tests and observe RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_chat_stream tests.test_langgraph_shadow -v
```

Expected: timing passes after Step 3; cancellation/API consistency tests still fail.

- [ ] **Step 6: Implement the async FastAPI bridge**

Make `/chat/stream` accept the Starlette `Request`. Use an async generator that advances the internal iterator through `asyncio.to_thread`, checks `await request.is_disconnected()`, yields only formatted v1 events, and always closes the iterator. Map dependency reasons to fixed safe error codes/messages; never include `str(error)`.

- [ ] **Step 7: Run focused streaming tests and observe GREEN**

Run the Step 5 command. Expected: all streaming and LangGraph tests pass.

### Task 5: Document, verify, review, and produce the framework diagram

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `docs/api-design.md`
- Modify: `docs/superpowers/plans/2026-07-14-langgraph-production-readiness-phase-2.md`
- Create: `/Users/seekinward/.codex/visualizations/2026/07/14/019f610f-3090-7170-a5b9-74a4a80ead64/phase-2-architecture.html`

**Interfaces:**
- Documents: the five Phase 2 settings, safe SSE behavior, disconnect behavior, retry boundary, and live Kimi smoke-test command.
- Produces: a visual architecture showing Java ownership, FastAPI guards, one LangGraph, safe stream buffer, validator, Kimi, RAG, PostgreSQL checkpoints, cancellation, and SSE events.

- [ ] **Step 1: Update templates and runtime documentation**

Add only the exact defaults from the approved design. Explicitly state that retry never occurs after public output and that deterministic non-model answers may arrive as one token event.

- [ ] **Step 2: Mark completed plan steps with evidence**

Change each completed checkbox only after its named RED/GREEN command has run. Add a short verification-results section with command, date, and pass/fail count.

- [ ] **Step 3: Run formatting and full Python verification**

Run:

```bash
git diff --check
.venv/bin/python -m unittest discover -v
.venv/bin/ruff check clothing_assistant tests
```

Expected: zero diff whitespace errors, all tests pass, and Ruff reports no errors in changed Phase 2 files (legacy unrelated findings must be reported separately, never hidden).

- [ ] **Step 4: Run cross-project contract verification**

Run:

```bash
python3 -m unittest tests.test_reproducible_environment -v
cd IntelligentOutfitRecommendationSystem/backend && sh ./mvnw -q -Dtest=RestPythonAssistantClientTests test
cd ../.. && docker compose -f IntelligentOutfitRecommendationSystem/docker-compose.yml config --quiet
```

Expected: environment tests, Java client tests, and Compose validation pass.

- [ ] **Step 5: Review against both development documents**

Check every Phase 2 acceptance row in the overall design and every section in the detailed design. Report any intentionally deferred Phase 3 work separately. Do not claim live PostgreSQL/Kimi verification unless it was actually run.

- [ ] **Step 6: Generate and verify the framework diagram**

Use the `visualize` skill to create the requested interactive architecture diagram in the visualization workspace. Verify it renders and link it in the final handoff.

## Plan Self-Review

- **Overall design coverage:** True tokens, sync/stream shared facts, disconnect cancellation, LLM/RAG timeout and retry, safe fallback, and unchanged SSE fields are each assigned to a task.
- **Detailed design coverage:** Safety tail, no retry after public output, bounded concurrency, error enums, deterministic paths, configuration validation, and secret-free tests are explicit.
- **Type consistency:** `stream_chat_content`, `SafeTokenBuffer`, `AgentStreamEvent`, and `stream_langgraph_agent` have one spelling and one owner throughout.
- **Scope:** Metrics dashboards, feedback persistence, provider failover, WebSocket, distributed limiting, and Phase 3 work are excluded.
- **Placeholder scan:** No TBD, TODO, “similar to”, or unspecified implementation step remains.
