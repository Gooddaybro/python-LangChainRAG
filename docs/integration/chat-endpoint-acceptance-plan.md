# `/chat` v0.1 Acceptance And Development Plan

Status: draft for review  
Scope: Python FastAPI `POST /chat` only  
Decision owner: Python AI service and Java `assistant-service`

## 1. Purpose

This document defines how we will验收 and then implement the Java-to-Python synchronous chat contract.

The first development checkpoint is not package refactoring. It is to make `POST /chat` stable enough for Java `assistant-service` to call, trace, and persist results.

This document is intentionally narrow:

- Validate the current `/chat` contract shape.
- Identify gaps between current Python behavior and the Java/Python v0.1 contract.
- Define test cases before changing implementation.
- Keep legacy local endpoints working during migration.

## 2. Source Of Truth

For this checkpoint, use this contract as the source of truth:

- `docs/integration/java-python-chat-contract.md`
- `docs/integration/java-python-chat-interface-development.md`

Do not use `docs/contracts/python-ai-api-contract.md` as the implementation source for this checkpoint. That document describes an older/generic shape with fields such as `message`, `reply`, and `recommendations`. The current Java integration direction uses:

- request field: `query`
- response field: `answer`
- response field: `product_refs`
- response field: `suggested_actions`
- SKU/SPU candidate objects passed from Java through `candidates`

If both documents disagree, this checkpoint follows the v0.1 integration documents under `docs/integration/`.

## 3. Current Observed State

The repository already contains partial implementation for this checkpoint.

Implemented or mostly implemented:

- `clothing_assistant/api/schemas.py` defines:
  - `PythonChatRequest`
  - `PythonChatResponse`
  - `UserContext`
  - `ProductCandidate`
  - `ProductRef`
  - `SuggestedAction`
  - `LegacyChatRequest`
- `clothing_assistant/api/app.py` routes production `POST /chat` to `run_langgraph_agent`.
- `POST /chat` requires `request_id`, `session_id`, and `query`.
- `thread_id` falls back to `session_id` when Java does not send `thread_id`.
- `user_context` and `candidates` are passed into LangGraph.
- `clothing_assistant/agent/state.py` already includes Java context fields:
  - `request_id`
  - `session_id`
  - `thread_id`
  - `user_context`
  - `candidates`
- `clothing_assistant/agent/langgraph_executor.py` writes these fields into the initial LangGraph state.
- `tests/test_api.py` already covers several API-level contract behaviors.
- `tests/test_langgraph_shadow.py` already checks that Java request context appears in LangGraph debug output.

Known concerns to verify before development:

- Some source comments and documentation render with mojibake in terminal output. This does not block contract behavior, but we should avoid touching unrelated encoded text during this checkpoint.
- There are two API contract documents with different field names. This checkpoint must explicitly align to the `docs/integration/` v0.1 shape.
- `product_refs` currently appears to be returned as an empty list. That is acceptable for this checkpoint if documented as phase boundary.
- Candidate ranking and real product reference generation are intentionally out of scope for the first `/chat`验收.

## 4. Target Contract For This Checkpoint

### 4.1 Request

`POST /chat` accepts:

```json
{
  "request_id": "req-20260529-001",
  "session_id": "s-001",
  "thread_id": "s-001",
  "query": "我 175cm 70kg，想买一件适合通勤的外套",
  "chat_history": [],
  "user_context": {
    "user_id": 10001,
    "height_cm": 175,
    "weight_kg": 70,
    "preferred_styles": ["commute"]
  },
  "candidates": [
    {
      "spu_id": 1001,
      "sku_id": 2001,
      "name": "通勤轻薄外套",
      "color": "黑色",
      "size": "L",
      "sale_price": 299,
      "stock_status": "in_stock"
    }
  ],
  "debug": false
}
```

Required:

- `request_id`: non-blank string
- `session_id`: non-blank string
- `query`: non-blank string

Optional:

- `thread_id`: if missing or null, Python uses `session_id` as LangGraph `thread_id`
- `chat_history`: defaults to `[]`
- `user_context`: defaults to `{}`
- `candidates`: defaults to `[]`
- `debug`: defaults to `false`

### 4.2 Response

`POST /chat` returns:

```json
{
  "request_id": "req-20260529-001",
  "answer": "可以优先看通勤轻薄外套，黑色更适合日常通勤。",
  "intent": "recommendation",
  "product_refs": [],
  "suggested_actions": []
}
```

Response rules:

- `request_id` must equal the request `request_id`.
- `answer` must be user-visible natural language.
- `intent` comes from LangGraph debug state when available.
- `intent` falls back to `unknown` if the agent result does not expose intent.
- `product_refs` is always an array.
- `product_refs` remains `[]` in this checkpoint.
- `suggested_actions` is always an array.
- If LangGraph stops because of missing information, return:

```json
{
  "type": "ask_follow_up"
}
```

inside `suggested_actions`.

- `debug` is included only when request `debug=true`.

### 4.3 Error Response

Validation errors:

- Missing `request_id`: HTTP 422
- Blank `request_id`: HTTP 422
- Missing `session_id`: HTTP 422
- Blank `session_id`: HTTP 422
- Missing `query`: HTTP 422
- Blank `query`: HTTP 422

Internal errors:

```json
{
  "error": "internal_server_error",
  "request_id": "req-20260529-001",
  "message": "AI service failed to process the request."
}
```

Internal error rules:

- Do not expose stack traces, prompt text, file paths, secrets, or raw model errors.
- If `request_id` can be parsed from the incoming JSON body, echo it.
- If `request_id` cannot be parsed, return `request_id: null`.

## 5. Acceptance Checklist

The `/chat` checkpoint is accepted only when all items below are true.

API schema:

- `PythonChatRequest` rejects missing required fields.
- `PythonChatRequest` rejects blank `request_id`, `session_id`, and `query`.
- `PythonChatRequest` accepts extra fields in `user_context`, `candidates`, and `chat_history` for forward compatibility.
- Request model defaults optional arrays/objects to empty structures instead of `null`.

API routing:

- `POST /chat` calls `run_langgraph_agent`.
- `POST /chat` passes `query.strip()` as the user query.
- `POST /chat` passes `chat_history` as a list of dictionaries.
- `POST /chat` uses `thread_id` when provided.
- `POST /chat` uses `session_id` as `thread_id` when `thread_id` is missing.
- `POST /chat` passes `request_id`, `session_id`, `user_context`, and `candidates` into LangGraph.

Response wrapping:

- `request_id` is echoed.
- `answer` is copied from the agent result.
- `intent` is copied from `debug.intent_result.intent` when available.
- Missing intent becomes `unknown`.
- `product_refs` is present and is `[]`.
- `suggested_actions` is present and is `[]` unless missing information is detected.
- `debug=false` omits the `debug` field.
- `debug=true` includes the `debug` field.

LangGraph state and trace:

- Initial state includes `request_id`.
- Initial state includes `session_id`.
- Initial state includes `thread_id`.
- Initial state includes `user_context`.
- Initial state includes `candidates`.
- `run_started` trace includes `request_id`, `session_id`, `thread_id`, and `run_id`.
- Final debug output includes Java request context for troubleshooting.

Legacy compatibility:

- `POST /chat/pipeline` keeps accepting the legacy local request shape.
- `POST /chat/langgraph` keeps accepting the legacy local request shape.
- Java production integration must not use those legacy endpoints.

## 6. Test Plan

Run focused tests first:

```powershell
python -m unittest tests.test_api -v
python -m unittest tests.test_langgraph_shadow -v
```

Then run the full suite:

```powershell
python -m unittest discover -v
```

Required test cases:

- `GET /health` returns `{"status": "ok"}`.
- `/chat` calls the LangGraph executor with Java contract fields.
- `/chat` falls back from missing `thread_id` to `session_id`.
- `/chat` uses explicit `thread_id` when provided.
- `/chat` hides debug when `debug=false`.
- `/chat` includes debug when `debug=true`.
- `/chat` maps missing information to `suggested_actions=[{"type": "ask_follow_up"}]`.
- `/chat` rejects missing `request_id`.
- `/chat` rejects blank `request_id`.
- `/chat` rejects missing `session_id`.
- `/chat` rejects blank `session_id`.
- `/chat` rejects missing `query`.
- `/chat` rejects blank `query`.
- `/chat` returns sanitized 500 errors.
- `/chat/pipeline` still works with legacy payload.
- `/chat/langgraph` still works with legacy payload.
- LangGraph debug includes `request_id`, `session_id`, `user_context`, and `candidates`.
- LangGraph first trace event for the current run includes `request_id` and `session_id`.

## 7. Development Steps After Approval

Do not start these steps until this document is reviewed and approved.

### Step 1: Establish baseline

Run:

```powershell
python -m unittest tests.test_api -v
python -m unittest tests.test_langgraph_shadow -v
```

Expected result:

- If tests pass, record the baseline and inspect whether any acceptance cases are still missing.
- If tests fail, fix only failures directly related to `/chat` contract behavior.

### Step 2: Fill missing tests

Add or adjust tests for acceptance cases not already covered.

Primary files:

- `tests/test_api.py`
- `tests/test_langgraph_shadow.py`

Do not change implementation until the missing or failing test clearly describes the desired behavior.

### Step 3: Patch API schema or app wrapper only if needed

Primary files:

- `clothing_assistant/api/schemas.py`
- `clothing_assistant/api/app.py`

Allowed changes:

- Request validation fixes.
- Response wrapper fixes.
- Error response fixes.
- Debug field inclusion/exclusion fixes.
- Thread/session fallback fixes.

Avoid:

- Candidate ranking.
- Real `product_refs` generation.
- Java internal API calls.
- Broad package refactoring.
- Streamlit UI changes.

### Step 4: Patch LangGraph context propagation only if needed

Primary files:

- `clothing_assistant/agent/state.py`
- `clothing_assistant/agent/langgraph_executor.py`
- `clothing_assistant/application/answer_service.py`

Allowed changes:

- Ensure Java context reaches initial state.
- Ensure Java context appears in debug.
- Ensure trace event includes request metadata.

Avoid:

- Changing graph topology.
- Changing intent routing rules.
- Changing tool selection behavior.

### Step 5: Run full verification

Run:

```powershell
python -m unittest tests.test_api -v
python -m unittest tests.test_langgraph_shadow -v
python -m unittest discover -v
```

Acceptance requires all relevant focused tests to pass. Full-suite failures outside this scope should be recorded separately instead of hidden inside this checkpoint.

## 8. Out Of Scope

This checkpoint does not implement:

- Real product ranking from `candidates`.
- Non-empty `product_refs`.
- `RequestCandidatesProvider`.
- `JsonProductFactProvider`.
- `JavaApiProductFactProvider`.
- Java internal API calls from Python.
- SSE streaming.
- MQ async tasks.
- Authentication.
- Retry policy.
- Timeout policy.
- Streamlit refactoring.
- Broad Python package migration.

These are later checkpoints after `/chat` v0.1 is accepted.

## 9. Open Decisions For Review

Please confirm these before development:

1. For this checkpoint, `product_refs=[]` is acceptable even when `candidates` is provided.
2. `suggested_actions` only maps `missing_info` to `ask_follow_up`; other action types wait for a later product-ranking checkpoint.
3. `docs/integration/` v0.1 contract overrides the older `docs/contracts/python-ai-api-contract.md` shape for current development.
4. Legacy endpoints `/chat/pipeline` and `/chat/langgraph` remain local/debug compatibility endpoints.

After these are confirmed, implementation should start from the test suite, not from refactoring.
