# FinAlly — Build Summary

**Status:** Complete. Built by a six-agent team; every component verified.

## Test Totals

| Suite | Count | Command |
|---|---|---|
| Backend (pytest) | **328** | `cd backend && uv run --extra dev pytest -q` |
| Frontend (Vitest + RTL) | **107** | `cd frontend && npm test -- --run` |
| End-to-end (Playwright) | **27** | `cd test && npm run e2e` |
| **Total** | **462** | |

`ruff check app tests` is clean; `tsc --noEmit` is clean. The backend suite was re-run under a
`socket.connect` guard rejecting any non-loopback address — all 328 pass with outbound network
fully blocked, so no test can reach OpenRouter even when a real key is present in `.env`.

## Component Map

| Area | Location | Notes |
|---|---|---|
| Market data | `backend/app/market/` | GBM simulator or Massive API; `PriceCache` + SSE. Pre-existing, frozen. |
| Database | `backend/app/db/` | SQLite, lazy init, seeded. `apply_trade()` is the single atomic cash+position transaction. |
| Services | `backend/app/services/` | Portfolio valuation, watchlist, session-open tracking for day change. |
| HTTP API | `backend/app/api/`, `app/main.py` | All `/api/*` routes, lifespan, snapshot task, static SPA serving. |
| LLM chat | `backend/app/llm/` | LiteLLM → OpenRouter → Cerebras, structured outputs, deterministic mock mode. |
| Frontend | `frontend/` | Next.js static export, TypeScript, Tailwind, Lightweight Charts. |
| Packaging | `Dockerfile`, `scripts/` | Multi-stage build, idempotent start/stop for macOS and Windows. |
| E2E | `test/` | Playwright against the production image on an isolated tmpfs database. |

## Architectural Decisions Made During the Build

These extend PLAN.md; `planning/CONTRACTS.md` holds the full interface detail.

- **Day change vs. tick change.** `PriceCache` reports tick-over-tick movement, which is not what a
  trader reads as "daily change". The watchlist service keeps a session-open map (first price seen
  per ticker, falling back to `SEED_PRICES`) and `/api/watchlist` returns the day change against it.
  SSE keeps emitting tick data for the flash animations. See CONTRACTS.md §4.2.
- **`GET /api/chat/history` was added** (not in PLAN.md §8) so the UI can restore a conversation
  after a page reload.
- **`create_stream_router()` registers onto a module-level router**, so two app instances would
  otherwise share routes and stream the wrong cache. `main.py` wraps it in `_scoped_stream_router`
  to bind each app to its own `PriceCache`.
- **The LLM layer depends on `typing.Protocol`s, not concrete services**, which let the LLM and API
  engineers build in parallel against a shared signature.
- **`ChatService` persists both chat rows itself**; the `/api/chat` route is a pure serialiser and
  must not write to `chat_messages` or it will double-write.
- **`list_chat_messages(limit)` returns the oldest N**, so "most recent N" requires widening the
  window and taking the tail — done in both `ChatService` and `/api/chat/history`.

## Bugs Found and Fixed During Verification

- **Container ignored SIGTERM.** `CMD ["sh","-c","uv run uvicorn ..."]` left un-`exec`'d process
  layers at PID 1, so `docker stop` never reached uvicorn: with a live SSE client it burned the full
  grace period and exited 137 with no shutdown logs. Now `exec uvicorn ... --timeout-graceful-shutdown 5`,
  stopping in ~6.2s at exit 0.
- **Startup snapshot never recorded.** `_snapshot_loop` took its first snapshot inside the loop, so a
  short-lived process was always cancelled before the first iteration. The lifespan now snapshots
  before creating the task, and the loop sleeps first.
- **`/api/chat/history` returned the oldest messages instead of the most recent.**
- **`.gitignore` had no `db/*.db` rule** and, being a Python-only template, no `node_modules/`,
  `frontend/.next/`, `backend/static/` or Playwright artifact coverage.

## Testing Gotchas Worth Remembering

- **`TestClient` never delivers `http.disconnect`**, so an abandoned SSE stream hangs shutdown
  forever. Drive the generator directly and `aclose()` the body iterator instead.
- **`BrowserContext.setOffline()` is not an SSE disconnect** — Chromium blocks new requests but
  leaves an already-streaming response intact. Bounce the container to genuinely sever the socket.
- **Never assert on the `flash-up`/`flash-down` classes** in E2E: the flash lasts ~500ms and the
  simulator ticks every ~500ms. Assert on price text.
- **Don't wait for `chat-loading`** under `LLM_MOCK=true` — it can last milliseconds. Wait for the
  assistant bubble.
- `chat-panel` collapses via the `hidden` attribute and stays mounted: use `not.toBeVisible()`.

## Running It

```bash
cp .env.example .env          # add OPENROUTER_API_KEY for real AI chat
./scripts/start_mac.sh        # or: pwsh scripts/start_windows.ps1
# http://localhost:8000
```

Without `OPENROUTER_API_KEY` everything works except live chat; set `LLM_MOCK=true` for
deterministic canned responses. Without `MASSIVE_API_KEY` the GBM simulator drives prices.
