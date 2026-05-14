---
name: building-production-rag-agent
description: Use when building, upgrading, or reviewing a RAG, LangGraph, AI customer-support, ecommerce assistant, knowledge-base assistant, or agentic workflow project that should become portfolio-ready or job-interview-ready rather than a quick demo.
---

# Building Production RAG Agent

## Core Principle

Build a usable AI application, not a notebook demo.

A project is not complete until it has a real interface, clear data flow, reliable retrieval or structured lookup, evaluation cases, error handling, a deployment path, and documentation that explains the architecture and tradeoffs.

## Target Outcome

The finished project should prove these abilities:

- Understand a real business scenario.
- Design a RAG or agentic workflow.
- Use structured data where precision matters.
- Use vector retrieval where semantic search matters.
- Expose the system through an API or UI.
- Test answer quality with realistic examples.
- Explain architecture clearly in README/docs.
- Run locally with predictable setup.

## Recommended Architecture

Use this default shape unless the existing project strongly suggests otherwise:

```text
frontend or API client
-> FastAPI backend or existing app entrypoint
-> LangGraph workflow
-> intent classification
-> missing-information check
-> structured lookup / RAG retrieval
-> answer generation
-> answer validation
-> logging and trace output
-> response
```

For ecommerce and sizing assistants, do not force everything through vector search:

```text
precise facts, numeric ranges, SKU data, stock, sizes -> structured lookup
policies, product descriptions, care guidance, style advice -> RAG retrieval
conversation control, branching, retries, validation -> LangGraph
```

## Workflow

1. Audit the current project before proposing changes.
   Identify entrypoints, data sources, retrieval code, graph/pipeline code, tests, docs, and local run commands.

2. Map the current flow.
   Write the actual path from user input to answer. Name each stage and its input/output state. Do not invent new architecture before understanding what exists.

3. Separate precision paths from semantic paths.
   Use structured lookup for values that must be exact, such as size tables, product IDs, measurements, price ranges, stock, shipping rules, and eligibility checks. Use RAG for explanatory or fuzzy knowledge.

4. Make orchestration explicit.
   Prefer a LangGraph workflow or a clearly equivalent pipeline with named nodes: router, memory/context resolver, missing-info gate, retriever/lookup, generator, answer checker, fallback.

5. Add evaluation before broad refactors.
   Create realistic cases that lock down routing, tool choice, retrieval behavior, answer safety, and fallback behavior. Keep deterministic tests separate from model-quality evals.

6. Expose the app.
   Provide either a backend API, a usable UI, or both. A script-only demo is not enough for a production-ready portfolio project.

7. Document architecture and tradeoffs.
   README should explain what problem the app solves, how data flows, where structured lookup is used, where RAG is used, how to run tests, and what limitations remain.

## LangGraph Node Checklist

Use these nodes as a reference shape. Keep names close to the existing codebase when possible.

| Node | Purpose | Output |
| --- | --- | --- |
| `intent_router` | Classify request type and scope | intent, query_type, confidence/reason |
| `context_resolver` | Use only relevant chat history | rewritten query, used history |
| `missing_info_gate` | Decide whether to answer or ask follow-up | missing fields, follow-up question |
| `structured_lookup` | Query exact tables/rules | matched record, reason, confidence |
| `rag_retriever` | Retrieve semantic context | chunks, sources, scores |
| `retrieval_grader` | Filter weak or irrelevant evidence | accepted/rejected evidence |
| `answer_generator` | Produce user-facing answer from evidence | draft answer |
| `answer_validator` | Check grounding, safety, and domain rules | final answer or retry/fallback |
| `trace_logger` | Persist debug evidence | trace events, metrics |

## Production Readiness Checklist

Before calling the project portfolio-ready, verify:

- Local setup works from a clean checkout.
- Environment variables are documented.
- App has an API endpoint or UI entrypoint.
- Retrieval/index rebuild path is documented.
- Structured data is stored in CSV, JSON, SQLite, or another parseable format when exact matching matters.
- RAG chunks include useful metadata for filtering.
- Answers cite or expose enough evidence for debugging.
- Unknown, out-of-scope, unsafe, and missing-information cases have explicit behavior.
- Tests cover routing, tool selection, structured lookup, RAG fallback, and answer validation.
- README includes architecture diagram or flow, setup, run, test, data update, limitations, and next steps.

## Evaluation Cases

Build a small but realistic eval set. For a customer-support or ecommerce assistant, include:

- Normal success cases.
- Missing information cases.
- Ambiguous follow-up cases that require chat history.
- Numeric or structured lookup cases.
- Product knowledge RAG cases.
- Policy/safety fallback cases.
- Out-of-scope cases.
- Conflicting evidence cases.

Each case should define expected intent, expected tool or node path, expected fallback behavior, and key facts that must or must not appear in the answer.

## Review Heuristics

When reviewing an existing project, prioritize findings in this order:

1. The app cannot be run, tested, or called through a stable interface.
2. The answer path is implicit or tangled, making behavior hard to debug.
3. Exact business logic is handled by vague RAG instead of structured data.
4. Retrieval has no metadata filtering, grading, or source trace.
5. The assistant guesses when information is missing.
6. There are no realistic eval cases.
7. README explains tools but not architecture, data flow, or tradeoffs.

## Common Mistakes

- Treating LangGraph as the goal. The goal is controllable business behavior; LangGraph is only the orchestration tool.
- Putting size tables, stock, prices, or eligibility rules only into vector chunks.
- Letting the LLM decide facts that should come from code or structured data.
- Building a chatbot UI while the retrieval and answer contracts are still untested.
- Mixing deterministic routing tests with subjective answer-quality evaluation.
- Claiming production readiness without setup, run, test, and data-refresh instructions.

## Portfolio Bar

A strong portfolio-ready RAG agent should let an interviewer see:

- What real user problem it solves.
- Why the workflow is split into these nodes.
- Why some data uses structured lookup and some uses vector retrieval.
- How failure cases are handled.
- How quality is measured.
- How the app would be deployed or extended.
