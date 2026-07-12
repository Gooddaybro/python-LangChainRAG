# LangGraph Production Readiness Phase 0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce Java candidate authority for production price/inventory answers and close the Phase 0 validation-log/debug-response exposure paths.

**Architecture:** Keep the existing single LangGraph graph. Add an explicit `allow_demo_catalog` execution flag that defaults to `False`; only local Streamlit/evaluation callers opt in. Production HTTP paths never opt in, so a price or inventory question with no Java candidates stops before local catalog matching. Keep debug payloads behind one fail-closed environment gate, while retaining the v1 request and response fields.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, LangGraph `StateGraph`, `unittest` and existing Java/Python v1 contract.

## Global Constraints

- Java owns products, SKUs, prices, inventory, sessions, authorization, and persisted messages.
- Python must not invent product IDs, price, stock, discount, order, payment, or after-sale facts.
- In production, `candidates` are the only product fact source for price/inventory answers; an empty candidate list must not trigger local catalog access.
- `product_refs` must remain traceable to current Java candidates.
- Do not add or rename Java-Python v1 fields. `debug` remains an existing request field, but production must fail closed unless explicitly enabled locally.
- Keep `/chat`, `/chat/stream`, token/done/error event names, and their field meanings compatible with v1.
- Validation logs must not include raw request bodies, Pydantic `input` values, Pydantic `ctx`, user profile values, candidate values, complete chat history, prompts, chunks, or secrets.
- Use test-driven development: run each new regression test and observe the expected failure before implementation.
- The repository has no initial Git commit. Do not stage, commit, reset, clean, or modify unrelated untracked files; reviewers inspect task-scoped files and test evidence instead of a Git diff package.

---

## File Structure

| File | Responsibility after Phase 0 |
| --- | --- |
| `clothing_assistant/agent/state.py` | Carries the explicit, per-run demo catalog opt-in. |
| `clothing_assistant/agent/langgraph_executor.py` | Defaults every caller to production fact behavior and passes the flag into the graph state. |
| `clothing_assistant/agent/nodes.py` | Stops price/inventory requests without Java candidates before any local catalog matching; retains JSON catalog only for explicit demo callers. |
| `clothing_assistant/ui/app_qa.py` | Explicitly marks the local debugging workbench as a demo catalog consumer. |
| `clothing_assistant/agent/eval_report.py` and `answer_quality_report.py` | Explicitly opt fixture-based local reports into the demo catalog. |
| `clothing_assistant/config_data.py` | Exposes one fail-closed `is_debug_response_enabled()` setting. |
| `clothing_assistant/api/app.py` | Hides debug output by default and writes only sanitized 422 diagnostics. |
| `tests/test_langgraph_production_nodes.py` | Proves production requests cannot obtain local price/inventory facts. |
| `tests/test_api.py` | Proves debug gating and no sensitive values in validation logs. |
| `docs/data-boundary.md` and `docs/api-design.md` | Document the production/demonstration split and debug policy. |

### Task 1: Enforce Java candidate authority for LangGraph product facts

**Files:**
- Modify: `clothing_assistant/agent/state.py`
- Modify: `clothing_assistant/agent/langgraph_executor.py`
- Modify: `clothing_assistant/agent/nodes.py`
- Modify: `clothing_assistant/ui/app_qa.py`
- Modify: `clothing_assistant/agent/eval_report.py`
- Modify: `clothing_assistant/agent/answer_quality_report.py`
- Modify: `tests/test_langgraph_production_nodes.py`
- Modify: `tests/test_langgraph_shadow.py`
- Modify: `docs/data-boundary.md`
- Test: `tests/test_langgraph_production_nodes.py`, `tests/test_langgraph_shadow.py`, `tests/test_eval_report.py`, `tests/test_answer_quality_report.py`

**Interfaces:**
- Produces: `run_langgraph_agent(..., allow_demo_catalog: bool = False) -> dict`
- Produces: `build_initial_state(..., allow_demo_catalog: bool = False) -> AgentState`
- Produces: `AgentState["allow_demo_catalog"]: bool`
- Produces on missing production facts: `debug.stop_reason == "missing_authoritative_candidates"`, `debug.missing_info_result["missing_fields"] == ["authoritative_candidates"]`, no `structured_lookup` call, and `product_refs == []`.
- Consumes: Java `candidates` unchanged; a non-empty list continues through `run_candidate_structured_lookup`.

- [x] **Step 1: Add failing production-fact regression tests**

Add two tests to `LangGraphProductionNodeTests`; do not pass `allow_demo_catalog`:

```python
def test_production_inventory_without_java_candidates_does_not_use_local_catalog(self):
    result = run_langgraph_agent(
        "基础款纯棉T恤黑色L码有货吗？",
        tool_registry=build_registry(),
        answer_generator=fake_answer_generator,
    )

    self.assertEqual(result["debug"]["stop_reason"], "missing_authoritative_candidates")
    self.assertEqual(result["debug"]["selected_tools"], [])
    self.assertEqual(
        result["debug"]["missing_info_result"]["missing_fields"],
        ["authoritative_candidates"],
    )
    self.assertEqual(result["product_refs"], [])
    self.assertNotIn("8 件", result["answer"])

def test_production_price_without_java_candidates_does_not_use_local_catalog(self):
    result = run_langgraph_agent(
        "基础款纯棉T恤多少钱？",
        tool_registry=build_registry(),
        answer_generator=fake_answer_generator,
    )

    self.assertEqual(result["debug"]["stop_reason"], "missing_authoritative_candidates")
    self.assertEqual(result["debug"]["selected_tools"], [])
    self.assertEqual(result["product_refs"], [])
    self.assertNotIn("99", result["answer"])
```

Change the existing local catalog tests `test_inventory_uses_structured_lookup_not_rag` and `test_price_uses_catalog_value` to pass `allow_demo_catalog=True`; they now verify the explicit demo-only path.

- [x] **Step 2: Run the focused tests and observe RED**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_langgraph_production_nodes.LangGraphProductionNodeTests.test_production_inventory_without_java_candidates_does_not_use_local_catalog \
  tests.test_langgraph_production_nodes.LangGraphProductionNodeTests.test_production_price_without_java_candidates_does_not_use_local_catalog -v
```

Expected: both tests fail because current code reads `product_catalog.json` and returns its stock/price.

- [x] **Step 3: Propagate the explicit demo flag through state construction**

Add `allow_demo_catalog: bool` to `AgentState`. Change the function signatures and state fields exactly as follows:

```python
def build_initial_state(
    user_query,
    chat_history,
    thread_id,
    run_id,
    request_id=None,
    session_id=None,
    user_context=None,
    candidates=None,
    demand_intent=None,
    allow_demo_catalog=False,
):
    return {
        # existing state fields
        "allow_demo_catalog": allow_demo_catalog,
    }

def run_langgraph_agent(
    user_query,
    chat_history=None,
    tool_registry=None,
    answer_generator=None,
    max_tool_calls=3,
    thread_id=None,
    request_id=None,
    session_id=None,
    user_context=None,
    candidates=None,
    demand_intent=None,
    use_cached_graph=False,
    allow_demo_catalog=False,
):
```

Pass `allow_demo_catalog=allow_demo_catalog` to `build_initial_state`. The default must remain `False`.

- [x] **Step 4: Stop before local catalog matching in production mode**

At the beginning of the price/inventory branch in `missing_info_gate_node`, add this branch before calling `find_matching_product`:

```python
if intent in {INTENT_INVENTORY_CHECK, INTENT_PRICE_CHECK}:
    candidates = state.get("candidates", [])
    if not candidates and not state.get("allow_demo_catalog", False):
        result = {
            "missing_fields": ["authoritative_candidates"],
            "can_continue": False,
            "reason": "java_candidates_missing",
        }
        return {
            "missing_info_result": result,
            "answer": "当前无法读取商品实时数据，暂时不能核实价格或库存，请稍后重试。",
            "final_prompt": "missing authoritative Java candidates; no local catalog lookup.",
            "stop_reason": "missing_authoritative_candidates",
            "trace_events": make_trace(
                "missing_info_gate",
                can_continue=False,
                missing_fields=result["missing_fields"],
                reason=result["reason"],
            ),
        }
```

Do not call `find_matching_product`, `extract_requested_color`, or `run_structured_lookup` in this branch. Keep the existing `candidates` behavior unchanged. `run_catalog_lookup` may retain the local JSON fallback only because every reachable caller without candidates is now explicit demo mode.

- [x] **Step 5: Mark local-only callers explicitly**

Pass `allow_demo_catalog=True` in these local-only call sites:

```python
# clothing_assistant/ui/app_qa.py
return langgraph_runner(
    clean_query,
    chat_history=chat_history,
    allow_demo_catalog=True,
)

# clothing_assistant/agent/eval_report.py
runner_kwargs = {
    "chat_history": case.get("chat_history"),
    "tool_registry": tool_registry,
    "answer_generator": answer_generator,
}
if executor_name == "langgraph":
    runner_kwargs["allow_demo_catalog"] = True
result = executor_fn(case["query"], **runner_kwargs)

# clothing_assistant/agent/answer_quality_report.py
result = agent_runner(
    case["query"],
    chat_history=case.get("chat_history"),
    tool_registry=tool_registry_factory(case.get("tool_fixture")),
    answer_generator=answer_generator,
    allow_demo_catalog=True,
)
```

Update mocks and direct tests that assert exact LangGraph call arguments. Do not add this flag to `/chat`, `/chat/stream`, or `/chat/langgraph`.

- [x] **Step 6: Update the data-boundary document**

Replace the current production interpretation of `product_catalog.json` in `docs/data-boundary.md` with an explicit statement:

```text
`product_catalog.json` is a standalone demo/test fixture. It is reachable only
when `allow_demo_catalog=True`; production HTTP requests must obtain price,
inventory, SKU, and color/size availability from Java `candidates`.
```

Document the `missing_authoritative_candidates` safe outcome and state that general advisory answers without candidates remain possible, but price/inventory facts and `product_refs` do not.

- [x] **Step 7: Run focused tests and observe GREEN**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_langgraph_production_nodes \
  tests.test_langgraph_shadow \
  tests.test_eval_report \
  tests.test_answer_quality_report -v
```

Expected: all listed tests pass; production tests show no local fact leakage, and explicit demo reports retain existing fixture expectations.

### Task 2: Fail closed for debug output and remove sensitive 422 log output

**Files:**
- Modify: `clothing_assistant/config_data.py`
- Modify: `clothing_assistant/api/app.py`
- Modify: `clothing_assistant/api/schemas.py`
- Modify: `tests/test_api.py`
- Modify: `docs/api-design.md`
- Test: `tests/test_api.py`, `tests/test_shared_contract.py`

**Interfaces:**
- Produces: `is_debug_response_enabled() -> bool`, true only when `DEBUG_RESPONSE_ENABLED` is exactly `"true"` ignoring case and surrounding whitespace.
- Produces: API debug output only when both `request.debug` and `is_debug_response_enabled()` are true.
- Produces: one 422 warning containing request id, method, path, and sanitized error metadata; it must contain no raw request value.
- Consumes: the unchanged `debug: bool` field in the v1 request schema.

- [x] **Step 1: Add failing API tests for debug gating and validation logging**

Add these tests to `ApiTests`:

```python
def test_chat_hides_debug_when_debug_responses_are_disabled(self):
    fake_result = {
        "answer": "fake answer",
        "debug": {"intent_result": {"intent": "chat"}, "trace_events": [{"step": "secret"}]},
    }
    with (
        patch("clothing_assistant.api.app.run_langgraph_agent", return_value=fake_result),
        patch("clothing_assistant.api.app.is_debug_response_enabled", return_value=False),
    ):
        response = self.client.post(
            "/chat",
            json={
                "request_id": "req-debug-disabled",
                "session_id": "session-debug-disabled",
                "query": "你是谁？",
                "debug": True,
            },
        )

    self.assertEqual(response.status_code, 200)
    self.assertNotIn("debug", response.json())
    self.assertNotIn("trace_events", response.text)

def test_chat_includes_debug_only_when_enabled(self):
    fake_result = {"answer": "fake answer", "debug": {"intent_result": {"intent": "chat"}}}
    with (
        patch("clothing_assistant.api.app.run_langgraph_agent", return_value=fake_result),
        patch("clothing_assistant.api.app.is_debug_response_enabled", return_value=True),
    ):
        response = self.client.post(
            "/chat",
            json={
                "request_id": "req-debug-enabled",
                "session_id": "session-debug-enabled",
                "query": "你是谁？",
                "debug": True,
            },
        )

    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.json()["debug"], fake_result["debug"])
```

Extend `test_chat_validation_error_does_not_echo_sensitive_body` with patched `logger.warning` and `logger.error`. Concatenate every positional argument from those mock calls and assert neither `secret-color` nor `secret candidate` occurs. Assert `logger.error` was not called by the validation handler.

- [x] **Step 2: Run the focused tests and observe RED**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_api.ApiTests.test_chat_hides_debug_when_debug_responses_are_disabled \
  tests.test_api.ApiTests.test_chat_includes_debug_only_when_enabled \
  tests.test_api.ApiTests.test_chat_validation_error_does_not_echo_sensitive_body -v
```

Expected: the disabled-debug test fails because `debug=true` is currently returned, and the validation-log test fails because current `logger.error` calls contain the complete request body.

- [x] **Step 3: Add the fail-closed debug configuration**

Add this function to `clothing_assistant/config_data.py`:

```python
def is_debug_response_enabled() -> bool:
    """Return whether this local process may expose internal debug payloads."""
    return os.getenv("DEBUG_RESPONSE_ENABLED", "false").strip().lower() == "true"
```

Import it in `clothing_assistant/api/app.py`. Change `build_contract_chat_response` so it computes:

```python
include_debug = include_debug and is_debug_response_enabled()
```

before constructing `PythonChatResponse`. Apply the same effective condition in `build_legacy_chat_response`, so legacy local endpoints do not bypass the production fail-closed setting. Update existing API tests that deliberately expect debug output to patch `is_debug_response_enabled` to return `True`.

- [x] **Step 4: Remove raw 422 request logging**

Replace the body-parsing and `logger.error` calls in `validation_exception_handler` with one warning:

```python
logger.warning(
    "422 validation error request_id=%s method=%s path=%s errors=%s",
    (safe_body or {}).get("request_id"),
    request.method,
    request.url.path,
    safe_errors,
)
```

Keep the existing safe 422 response body exactly as `{"detail": safe_errors, "body": safe_body}`. Do not log `request.json()`, `exc.errors()`, or any raw error `input`/`ctx` value. Remove the now-dead request-body try/except block.

- [x] **Step 5: Document the runtime policy without changing v1 fields**

In `clothing_assistant/api/schemas.py`, update the `debug` field description to state that it is honored only when the local service enables `DEBUG_RESPONSE_ENABLED=true`; it is otherwise suppressed. In `docs/api-design.md`, document:

```text
Production defaults to `DEBUG_RESPONSE_ENABLED=false`. `debug=true` is an
internal local-diagnostics request, not a client entitlement. Validation logs
record only request id, method, path, and sanitized field errors.
```

Do not change the field name, type, manifest, or response schema.

- [x] **Step 6: Run focused tests and observe GREEN**

Run:

```bash
.venv/bin/python -m unittest tests.test_api tests.test_shared_contract -v
```

Expected: all API and shared-contract tests pass. The debug field remains contract-compatible while disabled production calls receive no debug payload; 422 response and log assertions contain no sensitive values.

### Task 3: Close final-review validation identifier and API-documentation gaps

**Files:**
- Modify: `clothing_assistant/api/app.py`
- Modify: `tests/test_api.py`
- Modify: `tests/test_langgraph_production_nodes.py`
- Modify: `docs/api-design.md`
- Test: `tests/test_api.py`, `tests/test_langgraph_production_nodes.py`, `tests/test_shared_contract.py`

**Interfaces:**
- Produces: `extract_safe_request_id(request: Request) -> str | None`; it returns an ID only when the parsed JSON body is a dict and its `request_id` is a string matching `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`.
- Produces: 422 and global 500 response/log request identifiers only from `extract_safe_request_id`; invalid/missing IDs produce `null`/`None`, never a raw object, list, whitespace value, or oversized string.
- Produces: API documentation whose production `/chat` request, response, exact-fact, error, PowerShell, Java, and production-status examples all use v1 fields and Java `candidates` as the sole commerce fact source.

- [x] **Step 1: Add failing malformed request-id and no-catalog-call regressions**

In `tests/test_api.py`, add a helper that submits a validation-failing request with a sensitive invalid id, patches `logger.warning` and `logger.error`, then checks both response and log arguments:

```python
def assert_invalid_request_id_is_not_echoed_or_logged(self, invalid_request_id):
    secret = "raw-request-id-secret"
    with (
        patch("clothing_assistant.api.app.logger.warning") as mock_warning,
        patch("clothing_assistant.api.app.logger.error") as mock_error,
    ):
        response = self.client.post(
            "/chat",
            json={
                "request_id": invalid_request_id,
                "session_id": "session-invalid-request-id",
                "query": "   ",
            },
        )

    logged_text = " ".join(
        str(argument)
        for call in mock_warning.call_args_list
        for argument in call.args
    )
    self.assertEqual(response.status_code, 422)
    self.assertIsNone(response.json()["body"])
    self.assertNotIn(secret, response.text)
    self.assertNotIn(secret, logged_text)
    mock_error.assert_not_called()

def test_chat_does_not_echo_or_log_object_request_id(self):
    self.assert_invalid_request_id_is_not_echoed_or_logged({"trace": "raw-request-id-secret"})

def test_chat_does_not_echo_or_log_array_request_id(self):
    self.assert_invalid_request_id_is_not_echoed_or_logged(["raw-request-id-secret"])

def test_chat_does_not_echo_or_log_oversized_request_id(self):
    self.assert_invalid_request_id_is_not_echoed_or_logged("raw-request-id-secret" * 20)
```

In `tests/test_langgraph_production_nodes.py`, wrap each existing production no-candidate test in patches that would fail if a local catalog primitive is reached:

```python
with (
    patch("clothing_assistant.agent.nodes.find_matching_product", side_effect=AssertionError("local match called")),
    patch("clothing_assistant.agent.nodes.run_structured_lookup", side_effect=AssertionError("local lookup called")),
):
    result = run_langgraph_agent(...)
```

Import `patch` from `unittest.mock`. Keep the existing output assertions.

- [x] **Step 2: Run the new tests and observe RED**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_api.ApiTests.test_chat_does_not_echo_or_log_object_request_id \
  tests.test_api.ApiTests.test_chat_does_not_echo_or_log_array_request_id \
  tests.test_api.ApiTests.test_chat_does_not_echo_or_log_oversized_request_id -v
```

Expected: the malformed request-id tests fail because the current handler returns and logs the raw identifier. The no-catalog primitive patches should already pass only if Task 1's guard is truly before local matching.

- [x] **Step 3: Sanitize request identifiers before logs and error responses**

In `clothing_assistant/api/app.py`, import `re` and replace `extract_request_id` with:

```python
SAFE_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


async def extract_safe_request_id(request: Request) -> str | None:
    try:
        body = await request.json()
    except Exception:
        return None

    if not isinstance(body, dict):
        return None

    request_id = body.get("request_id")
    if not isinstance(request_id, str):
        return None

    return request_id if SAFE_REQUEST_ID_PATTERN.fullmatch(request_id) else None
```

Use this helper in both `global_exception_handler` and `extract_safe_request_body`. Do not log or return the raw `request_id` when the helper returns `None`; retain the existing safe response shape with `"body": None` for invalid IDs.

- [x] **Step 4: Align every production API example with v1 and the Java fact boundary**

Update `docs/api-design.md` with these exact facts:

1. The `/chat` request example and field table include required `request_id`, required `session_id`, optional `thread_id`, `query`, optional `chat_history`, optional `user_context`, optional `candidates`, optional `demand_intent`, and `debug`.
2. The normal response example includes `request_id`, `answer`, `intent`, `product_refs`, and `suggested_actions`; it is not an answer-only response.
3. The exact-fact section says Java `candidates`, not `product_catalog.json`, are the production price/inventory/SKU/color/size source. Its example includes an SKU candidate and describes an empty candidate list as `missing_authoritative_candidates`, no selected tool, no price/stock assertion, and no `product_refs`.
4. The 422 example includes only sanitized `detail` and `body` (request id or `null`); the 500 example is `{"error":"internal_server_error","request_id":"req-...","message":"AI service failed to process the request."}` and states it does not expose exception text.
5. PowerShell and Java examples include required v1 `request_id` and `session_id`, use `debug: false`, and pass Java-built candidates for exact fact questions.
6. Production-status and limitations sections say `product_catalog.json` is only an explicit `allow_demo_catalog=True` demo/test fixture; Java candidates are the production fact source.

Do not add fields or change schema names. Keep the debug requirement from Task 2: the debug payload is returned only when both `debug=true` and `DEBUG_RESPONSE_ENABLED=true`.

- [x] **Step 5: Run focused tests and documentation checks**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_api \
  tests.test_langgraph_production_nodes \
  tests.test_shared_contract -v
rg -n 'product_catalog\.json.*current structured data source|"detail": "error message"|"query".*基础款纯棉T恤.*"debug"' docs/api-design.md
```

Expected: all tests pass. The `rg` command prints no stale production catalog, old 500 detail, or incomplete request-example matches.

### Task 4: Restore the enforced API-module lint gate

**Files:**
- Modify: `clothing_assistant/api/app.py`
- Test: `clothing_assistant/api/app.py`, `tests/test_api.py`

**Interfaces:**
- Produces: no runtime/API contract change; only valid Google-style docstring formatting for public FastAPI helpers and handlers.
- Produces: `ruff check clothing_assistant tests` exits 0 with the repository's `pyproject.toml` rules.

- [x] **Step 1: Run Ruff and record the failing baseline**

Run:

```bash
.venv/bin/ruff check clothing_assistant tests
```

Expected: D200, D205, and D212 failures in `clothing_assistant/api/app.py`, caused by multiline docstrings whose summary line starts after the opening quotes or has no blank line before a description.

- [x] **Step 2: Make docstrings compliant without changing behavior**

In `clothing_assistant/api/app.py`, format each affected docstring using one of these exact forms:

```python
def simple_helper():
    """单句摘要。"""


def documented_handler():
    """单句摘要。

    第二段说明行为或边界。
    """
```

Apply this only to the functions reported by Ruff: `global_exception_handler`,
`build_legacy_chat_response`, `get_agent_intent`, `build_suggested_actions`,
`build_contract_chat_response`, `health`, `chat`, `generate_chat_stream`,
`chat_stream`, `chat_pipeline`, and `receive_feedback`. Preserve every function
signature, endpoint decorator, return value, log call, and request/response behavior.

- [x] **Step 3: Run lint and API regressions**

Run:

```bash
.venv/bin/ruff check clothing_assistant tests
.venv/bin/python -m unittest tests.test_api -v
```

Expected: Ruff prints `All checks passed!`; all API tests pass.

## Plan Self-Review

- **Spec coverage:** Task 1 implements the Phase 0 Java fact-source boundary and documents the demo exception. Task 2 implements debug fail-closed behavior and safe 422 logging. Task 3 sanitizes malformed identifiers in error paths and removes stale API examples that contradict the v1/Java-fact boundary. Task 4 restores the repository's enforced API-module lint gate without changing behavior. Deployment identity, persistent checkpointing, true SSE, and observability remain intentionally in later approved phases because they require separate persistence/provider decisions.
- **Scope:** The plan adds no new v1 field, database, queue, agent, or model provider. The demo catalog remains only where a local caller explicitly opts in.
- **Consistency:** `allow_demo_catalog` has one default (`False`) from `run_langgraph_agent` to `AgentState`; `missing_authoritative_candidates` has one stop reason; `DEBUG_RESPONSE_ENABLED` has one fail-closed parser.
- **Placeholder scan:** the four executable tasks contain no unresolved placeholders or deferred implementation steps.
