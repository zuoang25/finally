# FinAlly — Team Status Board

Shared coordination file. **Append only** — never delete or rewrite another agent's entry.
Read `planning/CONTRACTS.md` before you start; it is the authoritative interface contract.

## Team

| Role | Agent name | Boundary |
|---|---|---|
| Team Lead | (main session) | `planning/**`, `backend/pyproject.toml`, integration of the whole |
| Database Engineer | `db-engineer` | `backend/app/db/**`, `backend/tests/db/**` |
| Backend API Engineer | `backend-engineer` | `backend/app/{main,config}.py`, `app/api/**`, `app/services/**`, their tests |
| LLM Engineer | `llm-engineer` | `backend/app/llm/**`, `backend/tests/llm/**` |
| Frontend Engineer | `frontend-engineer` | `frontend/**` |
| DevOps Engineer | `devops-engineer` | `Dockerfile`, `docker-compose.yml`, `scripts/**`, `.env.example`, `.dockerignore` |
| Integration Tester | `integration-tester` | `test/**` |

## Build Order

1. **Wave 1 (parallel):** Database Engineer · Frontend Engineer · DevOps Engineer
2. **Wave 2 (parallel, after DB lands):** Backend API Engineer · LLM Engineer
3. **Wave 3:** Integration Tester (E2E against the built container), then fix cycles

---

## Progress Log

Append entries in this format:

```
### <agent name> — <ISO date> — <STARTED | DONE | BLOCKED>
- What landed (files, tests, counts)
- Anything downstream agents need to know
```

### team-lead — 2026-09-05 — STARTED
- Wrote `planning/CONTRACTS.md` (frozen interface contract: DB surface, HTTP shapes, LLM service
  protocol, frontend `data-testid` list, env vars).
- Pre-added every Python dependency to `backend/pyproject.toml` so no agent needs to edit it:
  added `pydantic`, `python-dotenv`, `litellm`, dev `httpx`.
- Confirmed toolchain on this machine: node 24.20.0, npm 11.19.0, uv 0.12.7, docker 29.7.2.
- Note: there is **no `.env` file** in the project root yet. All work must run green with
  `LLM_MOCK=true` and no API keys.

---

## Cross-Team Requests

Need something inside another agent's boundary? Append it here instead of editing their files.

```
### <requesting agent> → <owning agent>
- Request:
- Why:
```

### devops-engineer → team-lead
- Request: Add `db/*.db`, `db/*.db-wal`, `db/*.db-shm` to the root `.gitignore` (it currently
  only has the unrelated Django-style `db.sqlite3` entries).
- Why: PLAN.md §4 says `db/finally.db` should be gitignored; `.gitignore` isn't in my
  ownership list (only `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `scripts/**`,
  `.env.example`, `db/.gitkeep`, `.github/workflows/**`), so I'm flagging rather than
  editing it myself.

---

## Contract Change Requests

Think `CONTRACTS.md` is wrong? Append here and keep building against it as written.

```
### <agent> — <contract section>
- Problem:
- Proposed change:
```

### db-engineer — 2026-09-05 — DONE
- Implemented `backend/app/db/` per CONTRACTS.md section 3: `schema.sql` (6 tables +
  indexes on `(user_id, ticker)` for watchlist/positions, `(user_id, executed_at)` for
  trades, `(user_id, recorded_at)` for snapshots, `(user_id, created_at)` for chat),
  `connection.py` (`get_db_path`/`get_project_root`/`get_connection`/`init_db`, honoring
  `FINALLY_DB_PATH`, WAL + `foreign_keys=ON`, idempotent init), `seed.py` (default user +
  10-ticker watchlist), `models.py` (5 frozen `slots=True` row dataclasses with `to_dict()`),
  `exceptions.py` (`DbError` + `DuplicateTickerError`/`InsufficientFundsError`/
  `InsufficientSharesError`/`PositionNotFoundError`, human-readable messages), and
  `repositories.py` (every function from section 3.4, plus `apply_trade()` as the single
  atomic buy/sell transaction with `BEGIN IMMEDIATE` + rollback on failure). `__init__.py`
  re-exports the full public surface.
- Tests: `backend/tests/db/` — 63 new tests (136 total in the suite, all green), covering
  init_db idempotency, every repository happy path, weighted-avg-cost on repeat buys,
  avg-cost-unchanged + position-row-deleted on full sells, fractional shares, insufficient
  funds/shares (including rollback proof — cash/positions unchanged after a failed trade),
  duplicate-ticker on watchlist add, absent-ticker remove returning `False`, ordering
  (trades newest-first; snapshots/chat oldest-first), chat `actions` JSON round-trip
  (list of dicts and `None`), and per-user isolation on `apply_trade`/watchlist.
- `uv run --extra dev pytest -q`: 136 passed. `uv run --extra dev ruff check app tests`: clean.
- Contract ambiguities resolved:
  - `PositionNotFoundError` is defined/exported per spec but never raised by the db layer
    itself — section 3.7's trade maths only calls for `InsufficientSharesError` when selling
    a ticker with no position, so I left `PositionNotFoundError` available for the API/LLM
    layer's own use if needed.
  - `get_cash_balance` for a `user_id` with no `users_profile` row returns `0.0` rather than
    raising, and `set_cash_balance`/`apply_trade` upsert (`INSERT ... ON CONFLICT DO UPDATE`)
    the profile row rather than requiring one to pre-exist — this makes multi-user use safe
    by construction without a migration step, and only the seeded `"default"` user is relied
    on elsewhere in the plan.
  - `list_positions` ordering wasn't specified; I sorted by `ticker ASC` for determinism.
  - Insufficient-shares message format wasn't given verbatim (unlike the funds example) — I
    used `"Insufficient shares of {ticker}: need {needed:g}, have {have:g}"`.
- For Backend API / LLM engineers: import everything from `app.db` (see `__init__.py`'s
  `__all__`); `apply_trade` and `set_cash_balance` treat `user_id` as fully dynamic, so no
  special-casing is needed beyond passing `"default"`. All repo functions open/close their
  own connection — safe to call from thread-pooled sync route handlers.

### devops-engineer — 2026-09-05 — DONE (authoring); build verification partially blocked on in-progress work
- Authored all owned artifacts: `Dockerfile` (multi-stage: `node:20-slim` frontend export →
  `python:3.12-slim` runtime with `uv`, `FINALLY_DB_PATH=/app/db/finally.db`,
  `PYTHONUNBUFFERED=1`, non-root `finally` user owning `/app`, `HEALTHCHECK` against
  `/api/health` honoring `$PORT`, `CMD` runs uvicorn on `0.0.0.0:${PORT:-8000}`),
  `.dockerignore`, `docker-compose.yml` (named volume `finally-data`, `env_file` with
  `required: false` so a missing `.env` doesn't hard-fail compose), `.env.example`
  (documents all 5 vars from CONTRACTS.md §7), `db/.gitkeep`, and all four scripts:
  `scripts/start_mac.sh`, `scripts/stop_mac.sh`, `scripts/start_windows.ps1`,
  `scripts/stop_windows.ps1` (idempotent, `--build`/`-Build` flag, checks Docker
  installed/running, removes any prior same-name container, passes `--env-file .env` only
  if present with a note about `LLM_MOCK`/`OPENROUTER_API_KEY` otherwise, polls
  `/api/health` with a 60s timeout before printing the URL; stop scripts leave the
  `finally-data` volume intact).
- Verified:
  - `bash -n` on both `.sh` scripts: clean.
  - PowerShell `[System.Management.Automation.Language.Parser]::ParseFile` on both `.ps1`
    scripts: no syntax errors.
  - `docker compose config`: resolves cleanly (image name, port mapping, named volume,
    optional env file all correct).
  - `docker build --target frontend-build`: **succeeded** end-to-end against
    `frontend-engineer`'s code as of the time I ran it (npm ci → next build → static export
    to `frontend/out/`), confirming stage 1 layer ordering/caching is correct.
  - `docker build -t finally .` (full multi-stage): backend stage 2 was mid-flight
    (`uv sync --frozen --no-dev --no-install-project` was successfully resolving/downloading
    all deps — numpy, litellm, openai, tiktoken, etc. — from the lockfile) when the build was
    cancelled by BuildKit because the sibling frontend stage failed on that later pass —
    `frontend-engineer` had since added `src/app/page.tsx` importing
    `@/components/Terminal`, which doesn't exist yet. This is expected parallel-work churn,
    not a Dockerfile defect: my isolated frontend-only build immediately prior had succeeded.
  - `backend/app/main.py` does not exist yet either (backend-engineer/llm-engineer are Wave
    2, gated on DB landing per the Build Order above), so even a successful image build
    would not currently boot — `uvicorn app.main:app` has nothing to import.
  - Had to start Docker Desktop myself (was installed but not running) to get this far;
    it's up now.
- Not yet verified (blocked on other agents landing): a full `docker build -t finally .`
  success, container start, `curl /api/health` returning 200, and the UI loading on port
  8000. I'll re-run the full verification pass as soon as `frontend/src/components/Terminal`
  and `backend/app/main.py` land — no changes needed on my side to pick them up.
- Nothing outside my boundary was edited.

### team-lead — 2026-09-05 — Cross-Team Request resolved (devops-engineer → team-lead)
- Root `.gitignore` had no `db/*.db` rule, and being a Python-only template it also lacked
  `node_modules/`, `frontend/.next/`, `backend/static/` and Playwright artifact coverage.
- Appended a `# ---- FinAlly ----` section covering: `db/*.db{,-wal,-shm}`, `node_modules/`,
  `frontend/.next/`, `frontend/out/`, `frontend/next-env.d.ts`, `backend/static/`, and
  `test/{node_modules,test-results,playwright-report,blob-report}/`.
- Verified with `git check-ignore -v` on `db/finally.db`, `frontend/out/index.html`,
  `backend/static/index.html` and `node_modules/x` — all correctly ignored.
- devops-engineer: no action needed on your side. Stand by for the final build verification
  signal once backend-engineer and frontend-engineer land.

### llm-engineer — 2026-09-05 — DONE
- Implemented `backend/app/llm/` per CONTRACTS.md section 5:
  - `protocols.py` — `PortfolioServiceProtocol` (sync `get_portfolio`/`execute_trade`) and
    `WatchlistServiceProtocol` (async `get_watchlist`/`add_ticker`/`remove_ticker`), both
    `@runtime_checkable`, signatures exactly as section 5.1.
  - `schemas.py` — `Trade`, `WatchlistChange`, `AssistantResponse` (section 5.2), the frozen
    `ChatTurn` dataclass (`.message`/`.actions`/`.created_at`, plus `to_dict()`), and
    `parse_assistant_response()` which never raises (handles fenced JSON, JSON embedded in
    prose, plain prose, truncated JSON, a missing `message`, and partially invalid action
    entries — bad entries are dropped, not fatal).
  - `client.py` — `LLMClient` calling LiteLLM `completion` with model
    `openrouter/openai/gpt-oss-120b`, `extra_body={"provider":{"order":["cerebras"]}}`,
    `reasoning_effort="low"`, `response_format=AssistantResponse`, run via
    `asyncio.to_thread` so the event loop is never blocked. `litellm` is imported lazily, so
    `import app.llm` costs nothing and cannot fail without an API key. Any provider/network
    failure is wrapped in `LLMUnavailableError`.
  - `prompt.py` — persona prompt with cash, every position (qty/avg cost/price/market value/
    unrealized P&L/weight), totals, the watchlist with live prices (explicitly flagging
    tickers with no price as untradable), and the guardrail rules; `build_messages()` replays
    the last 10 chat rows as real `user`/`assistant` turns after the system message.
  - `mock.py` — the deterministic section 5.3 behaviour table.
  - `service.py` — `ChatService` running the full pipeline and returning `ChatTurn` with
    `actions` already in the section 4.8 wire shape.
- Tests: `backend/tests/llm/` — 76 new tests, all offline (no network, no `OPENROUTER_API_KEY`;
  the fixture deletes both `OPENROUTER_API_KEY` and `LLM_MOCK` and points `FINALLY_DB_PATH` at a
  per-test SQLite file). Covers every mock table row, ticker/quantity detection, structured
  output parsing (valid/malformed/missing-message/partially-invalid), each failure mode
  (`InsufficientFundsError`, `InsufficientSharesError`, `DuplicateTickerError`,
  `ValueError("No price available for X")`, invalid symbol, non-positive quantity, blank
  ticker, unexpected exception), one failed action not aborting the others, provider failure
  raising `LLMUnavailableError`, and both chat rows persisting with `actions` round-tripping.
- Full backend suite green (`uv run --extra dev pytest -q`: 267 passed) and
  `uv run --extra dev ruff check app tests` clean.

**For the Backend API Engineer — exact wiring:**
```python
from app.llm import ChatService, ChatTurn, LLMUnavailableError

chat_service = ChatService(portfolio_service=..., watchlist_service=...)   # in main.py
turn: ChatTurn = await chat_service.handle_message(body.message, user_id="default")
return {"message": turn.message, "actions": turn.actions, "created_at": turn.created_at}
```
- `handle_message` raises `ValueError("Message must not be empty")` for a blank message — map to
  **400** (you may also reject it at the Pydantic layer; both are fine).
- `handle_message` raises `app.llm.LLMUnavailableError` on provider failure — map to **503**
  `{"detail": f"AI assistant unavailable: {exc}"}` per section 4.8. Nothing else escapes: every
  trade/watchlist failure comes back as a `status: "failed"` action, never an exception.
- `ChatService` persists BOTH chat rows itself (`add_chat_message`) — the route must not persist
  anything, or messages will be duplicated. `GET /api/chat/history` just reads
  `list_chat_messages`.
- Your services only need to satisfy the protocols structurally; `ChatService` calls the sync
  portfolio methods via `asyncio.to_thread`, so they may block on SQLite safely.
- Optional constructor kwargs (defaults are what you want): `client=` to inject a custom
  `LLMClient`, `mock=True/False` to force mock mode. Left as `None`, mock mode is decided per
  request from `LLM_MOCK` — so flipping the env var needs no restart of the service object.

**For the Integration Tester:** with `LLM_MOCK=true`, message prefixes are exactly
`"Executed: bought "`, `"Executed: sold "`, `"Added "`, `"Removed "`, `"MOCK: "`. Note that a
mock ticker is only recognised if it is on the watchlist or in `SEED_PRICES` (AAPL, GOOGL, MSFT,
AMZN, TSLA, NVDA, META, JPM, V, NFLX) — so an "add" test should use a seeded ticker that has
been removed first, or a ticker already on the watchlist will come back as a `failed` action
(`"AAPL is already on the watchlist"`), which is per contract. Failed actions also append
`"Could not complete: <detail>."` to the end of `message`; the required prefix is unaffected.

---

## Contract Change Requests

### llm-engineer — section 3.4 / 5.4 (observation, not a blocker)
- Problem: `list_chat_messages(limit)` returns the OLDEST `limit` rows (`ORDER BY created_at ASC
  ... LIMIT ?`), so `list_chat_messages(limit=10)` yields the FIRST 10 messages of the
  conversation, not the last 10. Section 4.9's `GET /api/chat/history?limit=50` will likewise
  return the oldest 50 once a conversation exceeds that length.
- Proposed change: `list_chat_messages` should select the newest `limit` rows and return them
  oldest-first. I did not change it (db is outside my boundary); `ChatService` works around it
  by fetching a 500-row window and taking the tail. The Backend API Engineer may want the same
  workaround for `/api/chat/history`.

---

## Progress Log (continued)

### frontend-engineer — 2026-09-05 — DONE

**Scope:** `frontend/**` only. No files outside the boundary were touched (apart from this
append). No production-code changes were needed — the four new suites found no bugs.

**Final state**
- `cd frontend && npm test -- --run` → **107 tests, 13 files, all green** (was 59 across 9 files;
  +48 tests in 4 new files).
- `cd frontend && npm run build` → clean; static export lands in `frontend/out/`
  (`index.html`, `404.html`, `_next/`). `npx tsc --noEmit` is also clean.

**Tests added this session**
| File | Covers |
|---|---|
| `frontend/tests/chat.test.tsx` (18) | `ChatPanel` + the header toggle wired to it: history load from `/api/chat/history`, user vs assistant bubbles, action chips with `data-status`, `chat-loading` only while in flight, send/trim/clear, Enter-to-send, re-entrancy guard, `onActed` refresh only when actions were executed, 503 and non-API error banners, empty-conversation state, collapse/expand |
| `frontend/tests/header.test.tsx` (11) | `Header` money formatting, null/em-dash state, signed P&L colouring, `chat-toggle` label + `aria-expanded`; `ConnectionStatus` `data-status` for all three states |
| `frontend/tests/mainChart.test.tsx` (8) | `main-chart` / `main-chart-ticker`, live price + day change, up/down trace colour, no-ticker and no-ticks states, the two-point threshold |
| `frontend/tests/pnlChart.test.tsx` (11) | `pnl-chart` series derived from snapshots, live total appended as the trailing point, session delta + colour, 0/1-point degradation, bad-timestamp and non-finite filtering |

Everything is jsdom-only: `@/lib/api` is `vi.mock`ed per file and `EventSource`/`ResizeObserver`/
canvas are stubbed in `frontend/vitest.setup.ts`. No test needs a backend.

**Charting library:** TradingView **Lightweight Charts 5.0.9** (`lightweight-charts`), wrapped in
`frontend/src/components/LineChart.tsx` and used by `MainChart` and `PnlChart`. It is imported
lazily inside an effect so the static export never evaluates it in Node. It renders to `<canvas>`,
which jsdom cannot implement, so the two chart suites `vi.mock` the `LineChart` wrapper and assert
the series/colour their parent derives. Watchlist sparklines are hand-rolled inline SVG
(`Sparkline.tsx`), not the library.

**Contract §6.1:** all 41 `data-testid`s render. `main-chart`, `pnl-chart`, `portfolio-heatmap`,
`positions-table`, `watchlist` and `header-total-value` resolve through the `testId` prop of
`Panel.tsx` / `Header.tsx` rather than a literal attribute in the parent component — they are
present in the DOM either way, and are asserted in the unit suites.

**Notes for the Integration Tester**
- Build: `cd frontend && npm install && npm run build`; output directory is `frontend/out/`
  (`output: 'export'`, `trailingSlash: true`). Serve it from FastAPI at `/`.
- **Price flash is ~500 ms** (`FLASH_MS` in `frontend/src/hooks/usePriceFlash.ts`): the
  `flash-up` / `flash-down` class is added on a price change and removed 500 ms later. Do not
  assert on those classes in Playwright — the simulator ticks every ~500 ms, so the class is
  effectively racy. Assert on `watchlist-price-{TICKER}` **text** instead.
- `chat-loading` exists only while `/api/chat` is in flight. Against `LLM_MOCK=true` that can be
  a handful of milliseconds — assert on the resulting `chat-message-assistant` bubble rather than
  waiting for the spinner to appear.
- `chat-panel` collapses via the `hidden` attribute (it stays mounted), so `toBeHidden()` /
  `not.toBeVisible()` is the right assertion, not `toBeAttached()`.
- `main-chart` and `pnl-chart` draw only once they hold **two** points; before that they render
  explanatory copy inside the same container. The container testid is always present. The P&L
  curve needs two `portfolio_snapshots` rows (30 s apart) or one row plus a live total.
- Sparklines and the main chart accumulate from SSE **since page load**, so a freshly loaded page
  shows "awaiting stream" for a moment. Allow a couple of ticks (~1–2 s) before asserting on chart
  content.
- After any mutation the app refetches `/api/portfolio` and `/api/watchlist`, so header, positions,
  heatmap and P&L converge well inside the 5 s the contract allows.
- `watchlist-error`, `trade-error`, `trade-success` and `positions-empty` render **only** in their
  respective states — use `queryBy`/`not.toBeAttached()` for the negative case.

---

### backend-engineer — 2026-09-05 — DONE

Resumed after a session limit. The API layer (§4.1–§4.9), `main.py`, `config.py` and the two
services were already in place; this pass fixed the suite-blocking hang, closed the contract gaps
the LLM Engineer and Team Lead flagged, and ran the first real boot smoke test.

**Full suite: 328 passed in ~18 s, terminates cleanly. `ruff check app tests` clean.**

**1. The hang (`tests/api/test_app.py::test_each_app_streams_its_own_cache`)**

Cause was as diagnosed: `TestClient` never delivers `http.disconnect`, so the frozen
`_generate_events` loop in `app/market/stream.py` never saw `is_disconnected()` and shutdown blocked
on it forever. Fixed on the test side only — `app/market/**` is untouched.

The test now drives the SSE generator directly: it pulls the route off `app.routes` (which is what
makes it a genuine test of `_scoped_stream_router` — a stale route from the module-level router
would still be bound to a previous app's cache), calls it with a stub still-connected `Request`, and
closes `response.body_iterator` after the first `data:` event. `aclose()` raises `GeneratorExit` at
the generator's `yield`, so it ends immediately and deterministically: no fixed sleep, no reliance
on disconnect detection, whole file runs in 0.7 s. The assertion got stronger too — it now decodes
the payload and asserts the exact ticker set and prices per app, not just substring presence.

**2. Real bug found while fixing it: the startup snapshot never happened**

`_snapshot_loop` recorded its first snapshot inside the loop, so on a short-lived process the task
was cancelled before its first iteration ever ran — `test_records_a_snapshot_on_startup` failed
100% of the time once the file could run to completion. The lifespan now takes the startup snapshot
itself (`await _record_snapshot(...)`) before creating the task, and the loop sleeps first. A fresh
container therefore always leaves the P&L chart a starting point. Verified live: `/api/portfolio/history`
had a snapshot at boot and a second one immediately after a trade.

**3. Contract gaps closed**

- **§4.9 `/api/chat/history` was returning the OLDEST N, not the most recent N.** Exactly the issue
  the LLM Engineer filed. `app/api/chat.py` now has `_recent_chat_messages()`, which widens the
  `list_chat_messages` window until it stops coming back full and keeps the tail — correct even
  past the first page, unlike a single fixed fetch. Three tests cover it, including a
  `monkeypatch`ed small window that forces the widening path.
- **`ValueError` → 400** (per the LLM Engineer's mapping) rather than falling into the catch-all
  503. `LLMUnavailableError` → 503 is covered by a test using the real exception class.
- **Verified the route persists nothing.** `ChatService` writes both chat rows itself;
  `test_the_route_persists_nothing` asserts the history stays empty when a stub service returns a
  turn, so a future double-write would fail the suite.
- §4.5: added an exact key-set assertion on a position object (weight as a 0–100 percentage), the
  wire shape the frontend codes against. The other §4.5 rules (market-value ordering, `avg_cost`
  price fallback, zero cost basis → 0.0, rounding) were already covered in `tests/services/`.
- Added a bounded test that the snapshot loop keeps appending (5 s `asyncio.timeout`, no fixed sleep).

**4. Hermeticity with the new real `.env`**

`create_app` now passes `Settings.llm_mock` straight into `ChatService(mock=...)` instead of letting
it fall back to reading the ambient `LLM_MOCK`. An injected `Settings(llm_mock=True)` is therefore
authoritative and the mock path is guaranteed no matter what `.env` holds — tested in both
directions (`llm_mock=True` with `LLM_MOCK` deleted, `llm_mock=False` with `LLM_MOCK=true` set).

Verified rather than assumed: I re-ran the entire suite under a `socket.connect` guard that raises
on any non-loopback address. **328 passed with all outbound network blocked.** `MASSIVE_API_KEY` is
absent from `.env`, and `/api/health` reports `"market_data_source":"simulator"`.

`tests/api/test_chat.py::TestRealChatServiceInMockMode` now also exercises the app's *own*
`ChatService` end to end in mock mode — a conversational turn, an executed buy that moves the cash
balance, a failed trade reported as an action rather than raised, and both chat rows persisted once.

**5. Boot smoke test (`uv run uvicorn app.main:app --port 8000`)**

All green against the live GBM simulator: `/api/health` → `simulator`, 10 tickers tracked;
`/api/watchlist` → 10 tickers with live prices and day change measured against `SEED_PRICES`;
`/api/portfolio` → $10,000 flat; `/api/portfolio/trade` filled 2 AAPL at the live tick and returned
the updated portfolio; `/api/portfolio/history` showed the boot snapshot plus the post-trade one;
`/api/api/nope` → JSON 404, `/` → 200. `/api/stream/prices` streams for real: `retry: 1000` then
ticker-keyed maps of all 10 tickers every ~500 ms.

Shutdown is clean — a graceful Ctrl+Break gives `Application shutdown complete` / `Finished server
process` with **no "Task was destroyed but it is pending" warnings**.

**For the DevOps Engineer**
- uvicorn target: **`app.main:app`**, run with cwd `backend/` (`uv run uvicorn app.main:app --port 8000`).
- Static directory: **`backend/static/`** — `STATIC_DIR = Path(app/main.py).parents[1] / "static"`,
  i.e. copy the Next.js `frontend/out/` export to `/app/static` when the backend is at `/app`. It is
  optional: with no such directory `/` returns a JSON placeholder and the API still serves, so the
  image works before the frontend build lands.
- `FINALLY_DB_PATH=/app/db/finally.db` as planned; the lifespan `init_db()`s and seeds on boot.
- See the Cross-Team Request below about `--timeout-graceful-shutdown`.

## Cross-Team Requests (continued)

### backend-engineer → devops-engineer

**Add `--timeout-graceful-shutdown 5` (or similar) to the uvicorn command in the Dockerfile.**

Measured, not theoretical: with a browser holding the `/api/stream/prices` SSE connection open,
uvicorn logs `Waiting for connections to close. (CTRL+C to force quit)` and waits indefinitely — the
stream only ends when the client disconnects, and the app's lifespan shutdown runs after that. With
no client attached, shutdown is instant and clean. So `docker stop` on a container that a browser is
connected to will sit until Docker's 10 s grace period expires and then SIGKILL, which also skips
the lifespan (market data source `stop()`, snapshot task cancel). A graceful-shutdown timeout makes
the stop deterministic. Not a blocker for the build — the app is correct either way.

## Contract Change Requests (continued)

### backend-engineer — section 3.4 (observation, not a blocker)

Seconding the LLM Engineer: `list_chat_messages(limit)` returning the *oldest* `limit` rows means
neither consumer can ask for "the most recent N" directly — `app/llm/service.py` fetches 500 and
takes the tail, and `/api/chat/history` now widens its window until it stops filling. Both work.
If §3.4 is ever revisited, a `newest_first: bool = False` parameter (or a companion
`list_recent_chat_messages`) would remove the guesswork. **No change requested now** — the DB layer
is DONE and green, and this is not worth destabilising it.

### devops-engineer — 2026-09-05 — DONE (full verification complete)

Ran the full verification pass now that frontend and backend have landed.

- **`docker build -t finally .`**: succeeds end-to-end, both stages, against the real
  `frontend/` and `backend/app/main.py`. Frontend export → `Route (app) /` + `/_not-found`,
  `output: 'export'`; backend `uv sync` resolves and installs the full lockfile plus the
  project itself; static export lands at `/app/backend/static` as `main.py` expects.
- **Found and fixed a real bug** in the CMD, per backend-engineer's cross-team request:
  `CMD ["sh", "-c", "uv run uvicorn ..."]` left `sh` (and `uv run`) un-`exec`'d as PID 1, so
  `docker stop`'s SIGTERM never reached uvicorn — verified this concretely: with a live SSE
  client attached, `docker stop` took the full grace period and exit code was **137**
  (SIGKILLed), no shutdown log lines at all. Fixed by changing CMD to
  `["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
  --timeout-graceful-shutdown 5"]` — calling `uvicorn` directly off `PATH` (the venv's
  already synced in) instead of through `uv run` removes a second un-exec'd layer, and
  `exec` makes uvicorn itself PID 1. Re-verified after the fix: same live-SSE-client
  scenario, `docker stop` completed in **~6.2s** (under the 10s default grace period),
  **exit code 0**, and the logs show the SSE task cancelled by the graceful-shutdown timeout
  followed by `Application shutdown complete` / `Finished server process [1]` — lifespan
  shutdown now actually runs.
- **`/api/health`**: returns `{"status":"ok","market_data_source":"simulator","llm_mock":false,"tickers_tracked":10}`.
- **UI**: `GET /` serves the static export's HTML/JS/CSS correctly.
- **`/api/watchlist`** and **`/api/stream/prices`**: both verified live — watchlist returns
  the seeded 10 tickers with prices, SSE stream pushes ticker-keyed price updates
  continuously.
- **`.env` branches, both verified**:
  - With no `.env` present (temporarily moved the user's real `.env` aside, confirmed the
    163-byte file was restored byte-for-byte afterward): `start_mac.sh` prints the
    "no .env file found" note, container still starts and reaches healthy.
  - With the user's real `.env` present (`OPENROUTER_API_KEY` set, no `LLM_MOCK`): container
    picks it up via `--env-file`, health reports `llm_mock: false` as expected (contract:
    `LLM_MOCK` only truthy when explicitly `"true"/"1"/"yes"`).
- **Volume persistence**: watchlist `added_at` timestamps from an earlier run were still
  present after a full `stop` → `start` cycle, confirming `finally-data` survives container
  recreation.
- **Scripts — ran for real, not just parsed, on both platforms**:
  - `scripts/start_mac.sh` / `stop_mac.sh` (bash): first run, idempotent second run
    (tears down + recreates cleanly), stop, idempotent second stop (no-op, no error) — all
    verified across both the no-`.env` and with-`.env` branches above.
  - `scripts/start_windows.ps1` / `stop_windows.ps1` (native PowerShell, not WSL): same
    idempotent start/stop/re-stop sequence, verified against the running container. Health
    check polling, `--env-file` conditional, and container-removal-before-recreate logic all
    behaved as scripted.
- Left the app running and healthy at `http://localhost:8000` (via `scripts/start_mac.sh`,
  with the user's real `.env`) as the end state of this verification pass.
- `.gitignore` cross-team request: confirmed closed by team-lead (`git check-ignore -v`
  covers `db/*.db{,-wal,-shm}` etc.) — no further action needed from me.

**Definition of done, fully met**: `docker build -t finally .` succeeds; the container serves
`/api/health` and the UI on port 8000; prices stream over SSE; start/stop scripts work
idempotently on both bash and PowerShell, with and without `.env`; graceful shutdown with a
live SSE client is now clean and prompt. Nothing outstanding on my end.

---

### integration-tester — 2026-09-05 — DONE

**Scope:** `test/**` only. Nothing outside the boundary was edited apart from this append.

**Final state: 27 E2E tests, all green, against the production container.** Verified twice from
the host and once from the containerised Playwright service — three consecutive clean runs, no
flakes, ~36 s host / ~46 s in-container.

**What landed (`test/`)**
| File | Purpose |
|---|---|
| `docker-compose.test.yml` | App container (built from the unmodified production `Dockerfile`) + the official Playwright image on the same network. Browser deps stay out of the production image, per PLAN.md §12. |
| `playwright.config.ts` | One chromium project, `workers: 1`, `fullyParallel: false`, `retries: 0`. |
| `utils/global-setup.ts` | Reachability wait + `llm_mock === true` gate + pristine-database gate. |
| `utils/terminal.ts` | Every selector in the suite, plus the shared page helpers. |
| `utils/app-control.ts` | Forced SSE disconnect via the docker CLI or `/var/run/docker.sock`. |
| `specs/01..06` | The six scenario files below. |
| `README.md` | How to run it, both ways, and the house rules. |
| `package.json` / `tsconfig.json` | `npm run e2e`, `npm run typecheck` (tsc clean). |

**How to run**
```bash
cd test && npm install && npx playwright install chromium
npm run e2e                     # builds + starts the container, then runs the suite
E2E_HOST_PORT=8010 npm run e2e  # when 8000 is taken by a production `finally` container
docker compose -f docker-compose.test.yml run --rm playwright   # browser in a container
```

**Coverage (27 tests)**
- `01-fresh-start` (4) — the 10 seeded tickers each with a numeric price, day change and
  sparkline; exactly $10,000.00 cash, total == cash, `positions-empty`, zero heatmap tiles;
  `connection-status` = `connected` and prices genuinely moving; every panel present; AAPL
  selected by default; none of the transient banners rendered.
- `02-watchlist` (4) — remove NFLX (row and price cell both gone, list drops to 9); re-add it
  lower-case (server upper-cases per §4.3) and watch prices resume; duplicate `AAPL` add surfaces
  the 409 in `watchlist-error`; malformed `12345` rejected with the list unchanged; row click
  drives `main-chart-ticker` and pre-fills `trade-ticker-input`.
- `03-trading` (6) — buy 3 AAPL: `trade-success`, position opens, `avg_cost == fill price`,
  heatmap tile appears, cash falls by exactly `quantity x fill`, `header-total-value ==
  cash + qty x live price`. Partial sell: cash rises by the fill, quantity 3 -> 2, `avg_cost`
  unchanged (§3.7). Full sell: row and tile gone, `positions-empty` back, total == cash.
  Insufficient cash, insufficient shares and a non-positive quantity each surface in
  `trade-error` with cash untouched and no phantom position.
- `04-visualisations` (4) — one tile per position with the larger market value getting the larger
  rendered area; positions table quantity/avg cost/live price/P&L with
  `pnl == qty x (price - avg cost)`; `pnl-chart` draws its curve; `main-chart` follows selection
  from both the watchlist and the heatmap and draws the streamed trace.
- `05-chat` (7, all `LLM_MOCK=true`) — panel collapses via `hidden` and reopens; a conversational
  turn returns `MOCK:` with zero actions and an untouched book; `buy 3 NVDA` returns an
  `executed` `chat-action` chip and really moves cash, positions and the heatmap; the matching
  sell closes it; `buy 100000 AAPL` comes back as a `failed` chip with `Could not complete` in
  the message and cash unchanged; watchlist remove + re-add through chat; history survives a
  reload.
- `06-sse-resilience` (2) — reload rebuilds the stream; severing the stream flips the header dot
  off `connected` and it recovers, with prices ticking again, with no reload and no user action.

**Defects filed: none.** Every scenario in PLAN.md §12 passes against the built image. Backend
§4 shapes, §3.7 trade maths, §5.3 mock behaviour and all 41 §6.1 testids behaved exactly as
contracted — including the details other agents flagged for me (500 ms flash race, millisecond
`chat-loading`, `hidden`-based chat collapse, the two-point chart threshold).

**Testing notes worth keeping**
- 40 of the 41 §6.1 testids are exercised. The exception is `chat-loading`: under `LLM_MOCK=true`
  the request completes in milliseconds, so asserting the spinner appears is inherently racy
  (exactly as the Frontend Engineer warned). It is covered by the frontend unit suite instead.
- One deliberate structural exception to "select only on testids": the specs assert a `<canvas>`
  exists *inside* the `main-chart` / `pnl-chart` testids. Those containers always render — they
  show explanatory copy until they hold two points — so the container alone proves nothing and
  the canvas is the only evidence the chart actually has data. Flagged here rather than filed as
  a request for a new testid, since it is one assertion and the Frontend Engineer documented the
  canvas as the rendering mechanism.
- **`BrowserContext.setOffline()` is not a valid SSE disconnect** and my first attempt at
  `06-sse-resilience` failed because of it: Chromium's offline emulation blocks new requests but
  leaves an already-streaming response untouched, so the feed kept ticking and the dot stayed
  green. The spec now bounces the app container, which genuinely severs the socket and exercises
  EventSource's own retry. Worth knowing for anyone extending the suite.
- **Determinism:** `FINALLY_DB_PATH` points into a tmpfs, so every container start is a pristine
  $10,000 / empty book, fully isolated from the production `finally-data` volume. `global-setup`
  refuses to run against a dirty book rather than letting the fresh-start assertions fail
  confusingly. The suite never reads the project-root `.env` (no `env_file` in the test compose),
  so a real `OPENROUTER_API_KEY` cannot leak into a run — the chat specs are free by construction.
- No test asserts a frozen price or uses a fixed sleep. Money assertions are directional or are
  invariants computed from a single `page.evaluate` read, so the header and the position cells
  can never come from different paints.
- `06-sse-resilience` runs last because its restart resets the tmpfs database.

**For the DevOps Engineer:** the production `Dockerfile` built and ran clean for me unmodified —
`docker compose -f test/docker-compose.test.yml build finally-test` was fully cached off your
image, the container reached healthy in a couple of seconds, and `/api/health` reported
`{"status":"ok","market_data_source":"simulator","llm_mock":true,"tickers_tracked":10}`. The one
thing I overrode locally is the published host port (`E2E_HOST_PORT`), because your production
`finally` container was already holding 8000 while I tested. No changes needed on your side.

### integration-tester — 2026-09-05 — ADDENDUM (port default + rebuild against the DevOps exec fix)

- **Default host port is now 8100, not 8000.** `docker-compose.test.yml` publishes
  `${E2E_HOST_PORT:-8100}:8000` and `playwright.config.ts` defaults to the same, so `npm run e2e`
  needs no environment variables and can never fight a production `finally` container for 8000.
  In-container the app still listens on 8000, and the containerised Playwright service still
  targets `http://finally-test:8000` over the compose network.
- **Rebuilt and re-verified against the DevOps `exec` fix.** `docker compose build finally-test`
  picked up the new CMD; container reached healthy in ~2 s and `/api/health` reported
  `llm_mock: true` while the production `finally` container on 8000 reported `llm_mock: false`
  from the real `.env` — the two stacks ran side by side with no interference, which is the point.
- **Re-ran everything on the new default: 27/27 green from the host (32.2 s) and 27/27 from the
  Playwright container (41.2 s).** Five clean runs total across both execution paths, no flakes.
- **Volume isolation confirmed explicitly**, since it was raised: the `finally-test` service
  mounts **no volume at all**. `finally-data` is never referenced, and `FINALLY_DB_PATH` points
  into a tmpfs (`/tmp/e2e/finally.db`), so the database is destroyed and reseeded on every
  container start. A previous run's trades cannot reach a fresh-start assertion, and `global-setup`
  fails loudly rather than silently if the book is ever not pristine.
- Test stack torn down (`down -v`); the production `finally` container was left running and
  healthy on 8000, untouched.
