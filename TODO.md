# TODO

## Phase 1: Investigate + fix frontend fetch error
- [x] Confirm API_BASE usage and endpoint path mapping for quick extraction.
- [x] Add frontend fetch helper with URL diagnostics + improved error message for `extractPageQuick`.

## Phase 2: Multi-provider LLM support (automatic)
- [x] Add backend unified LLM provider abstraction (Anthropic, OpenAI, custom base_url+api_key).
- [x] Add backend endpoints to list available providers/models.
- [x] Add backend endpoint to test credentials/base_url.
- [ ] Refactor agent (claude_agent.py) to use selected provider+model for each chat.
- [ ] Extend websocket protocol to accept `{ provider, model, base_url?, api_key? }` in chat payload.



## Phase 3: Wire frontend UI
- [ ] Add UI settings panel (provider type, base URL, api key mode, model select) for best UX.
- [ ] Update `frontend/src/lib/api/agent.ts` and `boxlite-agent.ts` sendChat() to include selected provider/model.
- [ ] Add automatic model listing/testing UI flow.

## Phase 4: Validate
- [ ] Smoke test extractor quick endpoint from browser.
- [ ] Smoke test agent with Anthropic provider.
- [ ] Smoke test switching to OpenAI-compatible proxy.
- [ ] Smoke test switching to custom base_url+api_key provider.

