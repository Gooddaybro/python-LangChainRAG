# Stabilize Clothing RAG Agent MVP Design

## Goal

Stabilize the existing clothing guide agent MVP without changing its product direction. The agent should remain a small rule-router plus tool orchestration layer over the current RAG, size-rule, policy, and memory modules.

## Scope

This pass focuses on engineering hygiene:

- Make the project importable and testable as `clothing_rag_demo`.
- Keep generated runtime files out of git.
- Fix memory query construction so empty history is not injected into retrieval.
- Add minimal automated regression tests for routing, memory, tools, and package imports.
- Document setup and run commands.

This pass does not migrate to LangGraph, OpenAI Agents SDK, or a new vector database. It also does not redesign prompt strategy beyond changes needed to protect existing behavior.

## Architecture

The existing shape stays in place. `agent/agent_executor.py` remains the orchestration entry point, `agent/router.py` classifies user intent, and `tools/` wraps individual capabilities. Legacy `rag.py` stays available for the non-agent Streamlit path.

Imports should be package-qualified from repository root, so modules can be used by tests, scripts, Streamlit, and future deployment code without relying on the current working directory. The Streamlit scripts can still be launched from the project root.

## Behavior Rules

- Policy questions must not invent policies when no policy source exists.
- Size recommendations continue to use deterministic rules from `data/尺码推荐.txt`.
- Product and recommendation questions continue to retrieve knowledge chunks before final answer generation.
- Empty or irrelevant chat history should not be injected into retrieval text.
- Debug output remains available in the Streamlit expander, but normal answers stay user-facing.

## Testing

Use Python `unittest` first because this environment does not currently have `pytest` installed. Tests should avoid real model or embedding network calls where possible by covering deterministic router, memory, size, policy filtering, and import behavior.
