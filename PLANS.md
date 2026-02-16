# PLANS

## Muninn Cutover Plan (2026-02-16)

### Discovery Map (A-E)
- A) Incoming user message entry:
  - `backend/api/chat.py` -> `chat(request, payload)`
- B) Prompt/system context assembly:
  - `backend/core/chat_engine.py` -> `run_chat(...)`
  - `backend/core/prompt_builder.py` -> `build_messages(...)`
- C) Model response generation:
  - `backend/core/chat_engine.py` -> `llm_client.generate_messages(messages)`
  - `backend/core/llm.py` -> `LLMClient.generate_messages(...)`
- D) Post-processing and memory write path:
  - `backend/core/chat_engine.py` -> tool parse/execute, `memory_service.append_turn(...)`, `memory_service.maybe_consolidate(...)`
- E) Web UI response ingestion:
  - `backend/api/chat.py` -> JSON response body
  - `frontend/src/services/api.ts` -> `sendPrompt(...)`
  - `frontend/src/App.tsx` -> `handleSend()`

### Execution Checklist
- [x] Add MemoryProvider interface and Muninn HTTP provider (no vendoring)
- [x] Add factory with env selection and Muninn fallback
- [x] Wire pre-prompt `rehydrate` to `<SYSTEM_MEMORY>` injection
- [x] Wire post-response candidate staging + payload propagation
- [x] Add backend memory confirm relay endpoints
- [x] Add frontend minimal pending confirmation flow (Accept all / Reject all)
- [x] Add smoke script and run checks
- [x] Final docs pass + project memory update
