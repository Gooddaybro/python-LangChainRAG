# Copilot Instructions

This repository is a Python AI clothing shopping assistant with FastAPI, Streamlit, RAG, LangGraph, structured product lookup, and deterministic eval reports.

## Required Python Style

- Use Google Style Python Docstrings.
- Add type hints to all function parameters and return values.
- Add module, class, and public function docstrings when creating new code.
- Public function docstrings should include `Args:` and `Returns:`. Add `Raises:` when relevant.
- Comments should explain design reasons, business boundaries, or data-flow decisions.
- Avoid comments that merely repeat the code.

## Domain Rules

- Inventory, price, SKU, color availability, and size-rule facts must come from structured catalog data.
- RAG is only for explanatory knowledge such as color matching, washing care, style advice, and scenario recommendations.
- LangGraph nodes should update only the state fields they own.
- Fallback logic must be conservative when evidence is missing.
- Debug trace fields are for local development, tests, and eval reports; they should not leak into normal user-facing responses.

## Project-Specific Documentation Focus

- `clothing_assistant/agent/state.py`: explain why state fields exist and how they map to LangGraph/debug/eval responsibilities.
- `clothing_assistant/agent/nodes.py`: document node inputs, outputs, stop reasons, and routing boundaries.
- `clothing_assistant/agent/langgraph_executor.py`: document graph construction, conditional edges, and checkpoint/debug setup.
- `clothing_assistant/agent/tool_registry.py`: document tool selection criteria and result contracts.
- `clothing_assistant/tools/*.py`: document whether the tool returns exact facts or supporting evidence.
- `clothing_assistant/api/schemas.py`: use Pydantic `Field(description=...)` for external request and response fields.
- `clothing_assistant/agent/eval_*.py`: explain deterministic eval choices and why fake dependencies are used.

## Verification

Before proposing a change as complete, run the relevant local checks:

```powershell
python -m compileall -q clothing_assistant tests
python -m unittest discover -v
ruff check clothing_assistant tests
interrogate -v -i --fail-under=30 clothing_assistant
```
