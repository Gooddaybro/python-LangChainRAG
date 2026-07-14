# LangGraph Production Readiness Phase 2 Design

**Status:** Approved direction; detailed design pending user review.
**Scope:** Phase 2 of the Python/FastAPI/LangGraph service, continuing from the
uncommitted Phase 1 workspace.
**Goal:** Replace answer-after-completion chunking with safe model-time SSE,
cancel downstream work after client disconnect, and make model/RAG failures
bounded and classifiable without changing the Java-Python v1 contract.

## 1. Baseline

The current `/chat/stream` endpoint calls the synchronous
`run_langgraph_agent()`, waits for the entire answer, then splits the final text
with `iter_answer_chunks()`. This preserves the v1 SSE shape but is not real
streaming. The answer generator calls `ChatOpenAI.invoke()`, and neither the LLM
nor RAG boundary has an explicit shared timeout/retry classification policy.

Phase 0 and Phase 1 boundaries remain mandatory:

- Java owns authorization, users, sessions, products, prices, inventory,
  orders, payments, persisted messages, and frontend APIs.
- Python may only emit product references traceable to the current Java
  candidates.
- Pure RAG output may not invent prices, stock, SKU, or availability.
- Request payloads, prompts, raw chunks, tokens, and internal credentials must
  not enter durable checkpoints or external error responses.
- `/chat` remains available and keeps the existing v1 JSON fields.
- SSE remains `token`, `done`, and `error` with single-line JSON `data`.

Kimi's official API documentation confirms that its OpenAI-compatible chat API
supports `stream=True` and returns `text/event-stream`. The existing
`langchain-openai` dependency exposes synchronous and asynchronous streaming,
so Phase 2 does not add another model SDK.

## 2. Chosen Approach

Use one LangGraph business flow and introduce a streaming execution adapter at
the answer-generation seam. Deterministic graph work runs through the same
nodes and routing rules as `/chat`. When a model-generated answer is needed,
the adapter consumes model chunks as they arrive, keeps a bounded safety tail,
validates the cumulative candidate text with the existing deterministic fact
rules, and only releases safe text.

This approach was selected over:

1. Generating the whole answer and replaying chunks, which is not real
   streaming.
2. Calling the model twice, which increases cost and latency and still allows
   the second generation to drift from the validated first draft.

No second graph, multi-agent layer, broker, queue, or new streaming framework
is introduced.

## 3. Components and Interfaces

### 3.1 Model runtime policy

`clothing_assistant/infrastructure/llm_client.py` owns provider configuration
and error classification.

It will provide:

```python
class DependencyError(RuntimeError):
    dependency: str
    reason: str
    retryable: bool

def get_llm_timeout_seconds() -> float: ...
def get_llm_max_retries() -> int: ...
def get_llm_max_concurrency() -> int: ...
def stream_chat_content(messages, *, stop_requested=None) -> Iterator[str]: ...
```

The existing `ChatOpenAI` client is configured with explicit request timeout
and `max_retries=0`; retry ownership stays in one local wrapper. Retryable
conditions are provider 429, timeout, connection failure, and 5xx. Authentication,
validation, and other 4xx failures are not retried. Backoff is bounded, and a
single request never exceeds the configured attempt limit.

A process-local `BoundedSemaphore` caps simultaneous model generations. It is
not a distributed user-rate limiter; Java/gateway keeps that responsibility.

### 3.2 RAG runtime policy

The existing RAG tool remains synchronous and keeps its current return shape.
Its external embedding/vector operations receive explicit timeout settings and
the same bounded error vocabulary: `timeout`, `rate_limited`, `upstream_5xx`,
`connection_error`, or `invalid_response`.

Recoverable RAG failures return the existing empty-evidence result and route to
the existing safe fallback. They do not trigger an unbounded graph or model
retry. No raw provider exception or retrieved content is exposed through SSE.

### 3.3 Safe token buffer

`clothing_assistant/api/streaming.py` will own a small `SafeTokenBuffer` with
these rules:

- It accepts model text fragments and maintains the complete accumulated draft.
- It retains a configurable tail long enough for current forbidden-commerce
  patterns that may span provider chunk boundaries.
- Before releasing text, it applies the same pure-RAG commerce-fact predicate
  used by `answer_validator_node`.
- If a forbidden fact is detected, no part of the offending buffered text is
  emitted. Generation is closed and the stream ends with a safe `error` event.
- The final flush occurs only after the normal answer validator accepts the
  complete draft.
- Empty fragments and provider metadata never become token events.

For answers built deterministically from Java candidates, structured lookup,
size rules, direct answers, or fallback nodes, the adapter emits the already
validated text without invoking the model. Those paths do not pretend to be
provider token streams.

### 3.4 Graph streaming seam

The graph remains the source of routing and validation truth. A streaming run
uses the same initial state, checkpointer, tool registry, node functions,
generation-attempt limit, validator, response builder, and `product_refs`
builder as the synchronous run.

The executor will expose one streaming API:

```python
def stream_langgraph_agent(..., stop_requested=None) -> Iterator[AgentStreamEvent]: ...
```

`AgentStreamEvent` is internal only. It distinguishes candidate token text from
the final stable agent result. The API layer converts it to existing v1 SSE;
no internal graph event, prompt, trace, chunk, or tool payload crosses the
boundary.

On a normal run:

1. Execute deterministic nodes through the existing graph.
2. When model generation is required, consume actual provider chunks.
3. Release chunks through `SafeTokenBuffer`.
4. Run the existing answer validator on the complete draft.
5. Flush the safety tail only after acceptance.
6. Emit `done`; its `answer` must equal the exact concatenation of all emitted
   token contents.

If validation requests a retry, no rejected buffered text is emitted. The next
generation attempt uses the existing validation feedback and the existing
maximum of two attempts.

## 4. Cancellation

`/chat/stream` becomes async and checks `Request.is_disconnected()` while
waiting for graph/model output. A request-scoped cancellation signal is passed
to the streaming executor and provider iterator.

When disconnection is observed:

- Stop reading provider chunks and close the provider iterator.
- Do not invoke later graph nodes, retries, or response construction.
- Do not emit `done` or `error` because the client is gone.
- Release the model concurrency permit in `finally`.
- Record only a redacted cancellation reason with `request_id`/`run_id` when
  available; do not record accumulated answer text.

Cancellation is cooperative. No background generation task may outlive the
request after the iterator has been closed.

## 5. Error Semantics

The external v1 contract stays unchanged.

| Condition | SSE result | Retry |
| --- | --- | --- |
| Provider timeout/429/5xx before any safe token | `error` with stable dependency code | Bounded locally |
| Provider timeout/429/5xx after safe tokens | `error`; no `done` | Bounded only if no text was emitted |
| Forbidden commerce fact in buffered text | `error`; offending text withheld | Existing graph generation retry before emission |
| Final validator rejects after safe prefix release | `error`; no `done` | No retry after public output |
| RAG recoverable failure | Existing safe fallback answer | No graph loop |
| Client disconnect | No further event | No retry |

External messages are fixed and contain no exception string, token, prompt,
request body, candidate, or retrieved chunk. Internal logs use dependency and
reason enums, not raw payloads.

## 6. Configuration

Phase 2 adds documented, fail-closed parsers with conservative defaults:

```text
LLM_TIMEOUT_SECONDS=30
LLM_MAX_RETRIES=2
LLM_MAX_CONCURRENCY=8
RAG_TIMEOUT_SECONDS=20
STREAM_SAFETY_TAIL_CHARS=64
```

Timeouts must be positive, retries must be between 0 and 3, concurrency must be
at least 1, and the safety tail must be at least 32 characters. Invalid values
fail startup rather than silently disabling protection.

## 7. Testing and Acceptance

All new behavior is developed test-first with fake provider iterators and fake
clocks; tests do not contact Kimi, Jina, Java, PostgreSQL, or the network.

Required automated cases:

- The first SSE token is observed before the fake model iterator completes.
- `done.answer` equals the exact concatenation of emitted token contents.
- Provider chunks split across arbitrary boundaries produce correct text.
- A forbidden price/stock/SKU phrase spanning chunks is never emitted.
- A rejected generation retries only before public output and respects the
  existing generation-attempt limit.
- 429, timeout, connection failure, and 5xx use bounded retry counts and safe
  error codes; authentication/validation errors do not retry.
- A disconnected request closes the provider iterator, releases concurrency,
  and performs no later generation or `done` event.
- `/chat` and `/chat/stream` produce the same accepted answer,
  `product_refs`, stop reason, and factual boundary for the same deterministic
  input.
- Existing `/chat`, v1 JSON, SSE single-line JSON, Phase 0 fact boundaries,
  Phase 1 authentication, request-size, and checkpoint privacy tests remain
  green.

Completion evidence requires the focused streaming/resilience tests, all
Python tests, shared contract tests, Java client tests, and Compose validation.
A live-provider smoke test is documented separately and is not part of the
secret-free automated suite.

## 8. Non-Goals

- No changes to v1 JSON or SSE fields.
- No WebSocket, message queue, multi-agent architecture, or new model SDK.
- No Python-owned conversation persistence or distributed user rate limiting.
- No token/cost analytics dashboard; those remain Phase 3.
- No automatic failover to a second model provider.

## 9. Self-Review

- **Placeholders:** No TBD/TODO or unspecified external fields remain.
- **Consistency:** Real token output is produced only from provider chunks;
  deterministic answers are explicitly identified as non-provider paths.
- **Safety:** Rejected or forbidden buffered content is never emitted, and no
  retry occurs after public output has begun.
- **Scope:** Streaming, cancellation, and bounded dependency resilience are the
  only runtime changes; Phase 3 metrics and feedback work are excluded.
