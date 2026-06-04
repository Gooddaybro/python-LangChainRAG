# Project Coding Instructions

This repository is the Python AI project for the intelligent outfit shopping assistant.

## Shared Contract

Before changing AI chat, recommendation orchestration, RAG answers, SSE output, or Java-Python APIs, read:

- `..\outfit-project-contract\AGENTS.md`
- `..\outfit-project-contract\docs\business-rules.md`
- `..\outfit-project-contract\docs\coding-boundary.md`
- `..\outfit-project-contract\docs\dev-checklist.md`
- `..\outfit-project-contract\contracts\assistant-streaming-chat\v1.md`

The Python AI project is responsible for intent recognition, recommendation orchestration, RAG answers, ranking explanations, and natural language generation.
Product prices, inventory, order status, payment status, user ownership, and conversation persistence must come from Java-controlled APIs or Java-assembled request context.

## Boundary Rules

- Do not accept frontend calls as a replacement for Java authorization.
- Do not invent product, price, inventory, order, or payment facts.
- Do not return product references that cannot be traced to Java-provided candidates.
- Keep `/chat` available when adding `/chat/stream` so Java can roll out streaming gradually.
- Emit SSE `data` payloads as single-line JSON.

## Verification

Run the Python project's relevant tests before claiming Python runtime changes are complete.
Shared contract documentation-only changes do not require Python tests unless runtime code or contract validation tests are changed.
