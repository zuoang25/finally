# FinAlly — Interface Contracts

**This document is the authoritative contract between all team members.** It is frozen unless
the Team Lead changes it. If you believe a contract is wrong, append a note to
`planning/STATUS.md` under `Contract Change Requests` and continue with the contract as written —
do not unilaterally change a shape another agent is coding against.

Everything below extends `PLAN.md`; where the two disagree, this document wins on *shapes*
and `PLAN.md` wins on *intent*.

---

## 1. Ownership Map

Only touch files inside your own boundary. If you need a change in someone else's boundary,
write it into `planning/STATUS.md` under `Cross-Team Requests`.

| Owner | Paths |
|---|---|
| **Database Engineer** | `backend/app/db/**`, `backend/tests/db/**` |
| **Backend API Engineer** | `backend/app/main.py`, `backend/app/config.py`, `backend/app/api/**`, `backend/app/services/**`, `backend/tests/api/**`, `backend/tests/services/**` |
| **LLM Engineer** | `backend/app/llm/**`, `backend/tests/llm/**` |
| **Frontend Engineer** | `frontend/**` |
| **DevOps Engineer** | `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `scripts/**`, `.env.example`, `db/.gitkeep`, `.github/workflows/**` |
| **Integration Tester** | `test/**` |
| **Team Lead (already done)** | `backend/pyproject.toml` (all deps pre-added), `planning/**` |
| **Frozen — do not edit** | `backend/app/market/**`, `backend/tests/market/**` (shipped and reviewed) |

`backend/pyproject.toml` already contains every dependency the team needs: `fastapi`, `uvicorn`,
`numpy`, `massive`, `rich`, `pydantic`, `python-dotenv`, `litellm`, and dev extras `pytest`,
`pytest-asyncio`, `pytest-cov`, `ruff`, `httpx`. **Do not edit it.** If you genuinely need another
package, file a Cross-Team Request.

---

## 2. Existing Market Data Layer (frozen, already built)

```python
from app.market import (
    PriceUpdate,               # frozen dataclass
    PriceCache,                # thread-safe store
    MarketDataSource,          # ABC
    create_market_data_source, # factory: reads MASSIVE_API_KEY
    create_stream_router,      # FastAPI APIRouter factory for GET /api/stream/prices
)
from app.market.seed_prices import SEED_PRICES  # dict[str, float]
```

`PriceCache`: `update(ticker, price, timestamp=None)`, `get(ticker) -> PriceUpdate | None`,
`get_price(ticker) -> float | None`, `get_all() -> dict[str, PriceUpdate]`, `remove(ticker)`,
`.version` (monotonic int), `len()`, `in`.

`MarketDataSource`: `await start(tickers)`, `await stop()`, `await add_ticker(t)`,
`await remove_ticker(t)`, `get_tickers()`.

`PriceUpdate.to_dict()` →
```json
{"ticker":"AAPL","price":190.5,"previous_price":190.42,"timestamp":1757030400.5,
 "change":0.08,"change_percent":0.042,"direction":"up"}
```
Note: `change` / `change_percent` / `direction` here are **tick-over-tick**, not daily. Daily
change is computed separately — see §4.2.

---

## 3. Database Layer Contract (`backend/app/db/`)

The Database Engineer owns the implementation; the Backend API and LLM engineers code against
exactly this surface. Use the Python stdlib `sqlite3` module. All functions are **synchronous**
(FastAPI route handlers call them via `def` handlers or `run_in_threadpool`; the API engineer
decides). SQLite connections must be created per-call or per-thread — never share one connection
across threads.

### 3.1 Module layout

```
backend/app/db/
├── __init__.py       # re-exports the public surface below
├── schema.sql        # CREATE TABLE IF NOT EXISTS statements (exact schema from PLAN.md §7)
├── connection.py     # get_connection(), init_db(), DB_PATH resolution
├── seed.py           # seed_default_data(conn)
└── repositories.py   # the functions below (may be split into several modules)
```

### 3.2 Database path

```python
# connection.py
DEFAULT_DB_PATH = os.environ.get("FINALLY_DB_PATH", "db/finally.db")
```
Resolved relative to the **project root** (the parent of `backend/`) when relative. In Docker the
env var is set to `/app/db/finally.db`. `init_db()` must `mkdir -p` the parent directory.

### 3.3 Lazy initialisation

```python
def init_db(db_path: str | None = None) -> None:
    """Idempotent. Creates the parent dir, applies schema.sql, seeds default data
    if the users_profile table is empty. Safe to call on every startup."""
```
Connections must be opened with `check_same_thread=False`, `row_factory = sqlite3.Row`, and
`PRAGMA foreign_keys=ON`, `PRAGMA journal_mode=WAL`.

### 3.4 Public repository functions

All take `user_id: str = "default"` as their final keyword argument. Timestamps are ISO-8601 UTC
strings with a `Z` suffix produced by a shared `utcnow_iso()` helper. Ids are `uuid4().hex` strings.

```python
# ---- profile ----
def get_cash_balance(user_id: str = "default") -> float: ...
def set_cash_balance(balance: float, user_id: str = "default") -> None: ...

# ---- watchlist ----
def list_watchlist(user_id: str = "default") -> list[WatchlistRow]: ...
def add_watchlist_ticker(ticker: str, user_id: str = "default") -> WatchlistRow: ...
    # raises DuplicateTickerError if (user_id, ticker) already present
def remove_watchlist_ticker(ticker: str, user_id: str = "default") -> bool: ...
    # returns False if it was not present

# ---- positions ----
def list_positions(user_id: str = "default") -> list[PositionRow]: ...
def get_position(ticker: str, user_id: str = "default") -> PositionRow | None: ...
def upsert_position(ticker: str, quantity: float, avg_cost: float,
                    user_id: str = "default") -> PositionRow: ...
def delete_position(ticker: str, user_id: str = "default") -> None: ...

# ---- trades ----
def record_trade(ticker: str, side: str, quantity: float, price: float,
                 user_id: str = "default") -> TradeRow: ...
def list_trades(limit: int = 100, user_id: str = "default") -> list[TradeRow]: ...
    # newest first

# ---- snapshots ----
def record_snapshot(total_value: float, user_id: str = "default") -> SnapshotRow: ...
def list_snapshots(limit: int = 500, user_id: str = "default") -> list[SnapshotRow]: ...
    # OLDEST first (chart-ready, left to right)

# ---- chat ----
def add_chat_message(role: str, content: str, actions: list[dict] | None = None,
                     user_id: str = "default") -> ChatRow: ...
def list_chat_messages(limit: int = 50, user_id: str = "default") -> list[ChatRow]: ...
    # OLDEST first (render order)

# ---- atomic trade application ----
def apply_trade(ticker: str, side: str, quantity: float, price: float,
                user_id: str = "default") -> TradeRow: ...
    """Single transaction: validate funds/shares, update cash, upsert or delete the
    position, insert the trade row. Raises InsufficientFundsError / InsufficientSharesError
    and rolls back. This is the ONLY place cash and positions change together."""
```

### 3.5 Row types

Dataclasses (frozen, `slots=True`) exported from `app.db`, each with `to_dict()` returning exactly
the keys listed:

```python
WatchlistRow: id, user_id, ticker, added_at
PositionRow:  id, user_id, ticker, quantity, avg_cost, updated_at
TradeRow:     id, user_id, ticker, side, quantity, price, executed_at
SnapshotRow:  id, user_id, total_value, recorded_at
ChatRow:      id, user_id, role, content, actions (list[dict] | None, JSON-decoded), created_at
```

### 3.6 Exceptions

Exported from `app.db`, all subclassing `DbError(Exception)`:
`DuplicateTickerError`, `InsufficientFundsError`, `InsufficientSharesError`, `PositionNotFoundError`.
Each carries a human-readable `str(e)` suitable for surfacing in an HTTP 400 `detail` and in chat.

### 3.7 Trade maths (authoritative)

- **Buy**: `cost = quantity * price`; require `cash >= cost` (tolerance `1e-9`).
  New `avg_cost = (old_qty*old_avg + quantity*price) / (old_qty + quantity)`, rounded to 6 dp.
  New cash = `cash - cost`.
- **Sell**: require `position.quantity >= quantity` (tolerance `1e-9`).
  `avg_cost` is **unchanged** on a sell. New cash = `cash + quantity*price`.
  If the resulting quantity is `<= 1e-9`, delete the position row entirely.
- `quantity` must be `> 0`; fractional shares are allowed. `side` is `"buy"` or `"sell"`.
- Cash is stored unrounded; round only at the presentation layer.

---

## 4. HTTP API Contract

All routes are under `/api`. All responses are JSON. Errors use FastAPI's default shape:
`{"detail": "<human readable message>"}`.

Status codes: `400` for business-rule violations (insufficient cash/shares, bad ticker),
`404` for unknown resources, `409` for duplicate watchlist add, `422` for malformed bodies
(FastAPI default), `503` when no price is available for a ticker yet.

### 4.1 `GET /api/health`
```json
{"status":"ok","market_data_source":"simulator","llm_mock":true,"tickers_tracked":10}
```
`market_data_source` is `"simulator"` or `"massive"`.

### 4.2 `GET /api/watchlist`
```json
{"tickers":[
  {"ticker":"AAPL","price":190.50,"previous_price":190.42,"open_price":190.00,
   "change":0.50,"change_percent":0.263,"direction":"up","added_at":"2026-09-05T10:00:00Z"}
]}
```
- `previous_price` / `direction` are tick-over-tick, straight from `PriceCache`.
- `open_price` is the **session open**: the first price observed for that ticker since the process
  started, falling back to `SEED_PRICES[ticker]` when known. Backend API owns this map.
- `change` and `change_percent` in **this** payload are **daily**: `price - open_price` and
  `(price - open_price) / open_price * 100`. This is what the UI labels as the day change.
- `price` is `null` when the ticker has no price yet (just added, first tick pending); in that case
  `change`, `change_percent`, `open_price` are `null` and `direction` is `"flat"`.
- Order: watchlist order is by `added_at` ascending.

### 4.3 `POST /api/watchlist`
Request `{"ticker":"pypl"}` → **201** with a single item in the §4.2 shape.
- Ticker is upper-cased and trimmed server-side. Must match `^[A-Z][A-Z.\-]{0,9}$` else `400`.
- Already present → `409`.
- On success the backend must call `await source.add_ticker(TICKER)` so prices start flowing.

### 4.4 `DELETE /api/watchlist/{ticker}`
→ **204** no content. Not present → `404`. On success call `await source.remove_ticker(TICKER)`
**only if** the user holds no position in it (keep pricing positions you still own).

### 4.5 `GET /api/portfolio`
```json
{
  "cash_balance": 8050.00,
  "positions": [
    {"ticker":"AAPL","quantity":10.0,"avg_cost":190.00,"current_price":195.00,
     "market_value":1950.00,"cost_basis":1900.00,"unrealized_pnl":50.00,
     "unrealized_pnl_percent":2.6316,"weight":19.5}
  ],
  "positions_value": 1950.00,
  "total_value": 10000.00,
  "total_cost_basis": 1900.00,
  "total_unrealized_pnl": 50.00,
  "total_unrealized_pnl_percent": 2.6316
}
```
- `weight` is a **percentage of `total_value`** (0–100), not a fraction.
- `total_unrealized_pnl_percent` = `total_unrealized_pnl / total_cost_basis * 100`, or `0.0` when
  `total_cost_basis == 0`.
- `current_price` falls back to `avg_cost` when the cache has no price for a held ticker.
- Money fields rounded to 2 dp, percent fields to 4 dp, `quantity` to 6 dp.
- `positions` sorted by `market_value` descending.
- With no positions: `positions: []`, `positions_value: 0.0`, `total_value == cash_balance`.

### 4.6 `POST /api/portfolio/trade`
Request `{"ticker":"AAPL","quantity":10,"side":"buy"}` (quantity `> 0`, side `"buy"|"sell"`).
Response **200**:
```json
{"trade":{"id":"...","ticker":"AAPL","side":"buy","quantity":10.0,"price":195.00,
          "executed_at":"2026-09-05T10:01:00Z"},
 "portfolio":{ ...exactly the §4.5 shape... }}
```
- Fill price is `PriceCache.get_price(ticker)` at execution time. No price → `503`
  `{"detail":"No price available for XYZW"}`.
- Ticker not on the watchlist is still tradable **only if** a price exists; otherwise `400`.
- Insufficient cash / shares → `400` with the exception message.
- After a successful trade the backend records a `portfolio_snapshots` row immediately.

### 4.7 `GET /api/portfolio/history?limit=500`
```json
{"snapshots":[{"total_value":10000.00,"recorded_at":"2026-09-05T10:00:00Z"}]}
```
Oldest first. A background task appends a snapshot every 30 s while the app runs.

### 4.8 `POST /api/chat`
Request `{"message":"buy me 5 nvidia"}`. Response **200**:
```json
{
  "message":"Bought 5 NVDA at $138.20. Your tech weight is now 62% — that's concentrated.",
  "actions":[
    {"type":"trade","status":"executed","ticker":"NVDA","side":"buy","quantity":5.0,
     "price":138.20,"detail":"Bought 5 NVDA @ $138.20"},
    {"type":"trade","status":"failed","ticker":"TSLA","side":"buy","quantity":1000.0,
     "price":null,"detail":"Insufficient cash: need $250000.00, have $8050.00"},
    {"type":"watchlist","status":"executed","ticker":"PYPL","action":"add",
     "detail":"Added PYPL to watchlist"}
  ],
  "created_at":"2026-09-05T10:02:00Z"
}
```
- `actions` is always an array (empty when nothing was executed).
- `type` ∈ `{"trade","watchlist"}`; `status` ∈ `{"executed","failed"}`.
- Trade actions always carry `ticker,side,quantity,price,detail` (`price` `null` on failure);
  watchlist actions always carry `ticker,action,detail` where `action` ∈ `{"add","remove"}`.
- A failed action never aborts the request — it is reported in `actions` and the LLM's `message`.
- Empty/whitespace-only message → `400`.
- LLM/provider failure → `503` `{"detail":"AI assistant unavailable: <reason>"}`.

### 4.9 `GET /api/chat/history?limit=50`
```json
{"messages":[{"id":"...","role":"user","content":"buy me 5 nvidia","actions":null,
              "created_at":"2026-09-05T10:02:00Z"}]}
```
Oldest first. `actions` is `null` for user messages, an array for assistant messages.

### 4.10 `GET /api/stream/prices`
Already implemented in `app/market/stream.py` — do not modify. Emits `retry: 1000` then, on every
cache version change (~500 ms):
```
data: {"AAPL":{"ticker":"AAPL","price":190.5,"previous_price":190.42,"timestamp":1757030400.5,"change":0.08,"change_percent":0.042,"direction":"up"}, ...}
```
The payload is a **map keyed by ticker containing every tracked ticker**, not a single ticker.

---

## 5. LLM Service Contract (`backend/app/llm/`)

The LLM Engineer owns this module. The Backend API Engineer's `/api/chat` route calls exactly this:

```python
from app.llm import ChatService, ChatTurn

service = ChatService(portfolio_service=..., watchlist_service=...)  # injected in main.py
turn: ChatTurn = await service.handle_message(message: str, user_id: str = "default")
# ChatTurn: .message (str), .actions (list[dict] matching §4.8), .created_at (str)
```

`ChatService.handle_message` is responsible for the full pipeline: build context → call the LLM →
parse structured output → execute actions through the injected services → persist both the user and
assistant rows via `app.db.add_chat_message` → return `ChatTurn`. The route only serialises it.

### 5.1 Injected service protocols

The LLM Engineer defines these `typing.Protocol`s in `app/llm/protocols.py`; the Backend API
Engineer's services satisfy them structurally. **Both engineers must match these signatures.**

```python
class PortfolioServiceProtocol(Protocol):
    def get_portfolio(self, user_id: str = "default") -> dict: ...      # §4.5 shape
    def execute_trade(self, ticker: str, side: str, quantity: float,
                      user_id: str = "default") -> dict: ...            # §4.6 "trade" object
        # raises app.db.DbError subclasses, or ValueError("No price available for X")

class WatchlistServiceProtocol(Protocol):
    async def get_watchlist(self, user_id: str = "default") -> list[dict]: ...  # §4.2 items
    async def add_ticker(self, ticker: str, user_id: str = "default") -> dict: ...
    async def remove_ticker(self, ticker: str, user_id: str = "default") -> bool: ...
        # add_ticker raises DuplicateTickerError; both raise ValueError on a bad symbol
```

### 5.2 Structured output schema

```python
class Trade(BaseModel):
    ticker: str
    side: Literal["buy", "sell"]
    quantity: float

class WatchlistChange(BaseModel):
    ticker: str
    action: Literal["add", "remove"]

class AssistantResponse(BaseModel):
    message: str
    trades: list[Trade] = []
    watchlist_changes: list[WatchlistChange] = []
```

Call via the `cerebras-inference` skill: LiteLLM `completion`, model
`openrouter/openai/gpt-oss-120b`, `extra_body={"provider":{"order":["cerebras"]}}`,
`reasoning_effort="low"`, `response_format=AssistantResponse`. Run the blocking call in a thread
(`anyio.to_thread.run_sync` or `asyncio.to_thread`) so the event loop is not blocked.

### 5.3 Mock mode

When `LLM_MOCK=true`, `ChatService` must not import-time-fail or make any network call and must
return deterministic responses. Required deterministic behaviours (the Integration Tester's E2E
suite depends on **exactly** these — case-insensitive substring match on the user's message):

| User message contains | Mock behaviour |
|---|---|
| `"buy"` + a known ticker + a number | one executed buy trade of that quantity/ticker; message starts `"Executed: bought "` |
| `"sell"` + a known ticker + a number | one executed sell trade; message starts `"Executed: sold "` |
| `"add"` + a ticker | one `watchlist`/`add` action; message starts `"Added "` |
| `"remove"` + a ticker | one `watchlist`/`remove` action; message starts `"Removed "` |
| anything else | no actions; message starts `"MOCK: "` and includes the live cash balance and position count |

Ticker detection in mock mode: the first standalone uppercase-able token of 1–5 letters that is a
known ticker (watchlist ∪ `SEED_PRICES`). Quantity: the first number in the message.
Mock responses still flow through the real execution path, so a mock buy with insufficient cash
still produces a `failed` action — that is intended and tested.

### 5.4 System prompt

Persona "FinAlly, an AI trading assistant". Must include: current cash, every position with
quantity/avg cost/current price/unrealized P&L, total portfolio value, the watchlist with live
prices, and the last 10 chat turns. Instruct concise, data-driven answers; execute trades when
asked or agreed to; never invent prices; state that it may only use tickers with live prices.

---

## 6. Frontend Contract

Next.js (App Router) + TypeScript + Tailwind, `output: 'export'`, `images.unoptimized: true`,
`trailingSlash: true`. Build output goes to `frontend/out/`. No `next/font` remote fetches (the
Docker build has no network guarantee) — use system font stacks or a self-hosted font.

- Dev proxy: `frontend/next.config.ts` must rewrite `/api/*` to `http://localhost:8000/api/*` in
  dev only (`output: 'export'` ignores rewrites at export time, which is fine — production is
  same-origin).
- All fetches are relative (`/api/...`). Never hardcode a host.
- SSE: native `EventSource('/api/stream/prices')`; parse the ticker-keyed map from §4.10; track
  connection state for the header dot; rely on EventSource's built-in retry.
- Sparklines accumulate in client memory from the SSE stream since page load (cap ~120 points/ticker).
- Colours: accent yellow `#ecad0a`, blue primary `#209dd7`, purple secondary `#753991` (submit
  buttons), background `#0d1117`, up-green and down-red of your choosing. No pure black.
- Price flash: apply a CSS class on change, remove after ~500 ms.

### 6.1 Required `data-testid` attributes (contract with the Integration Tester)

The Integration Tester selects **only** on these. Frontend must render them exactly; Integration
Tester must not invent others.

| testid | Element |
|---|---|
| `app-root` | Top-level app container (present once hydrated) |
| `connection-status` | Header status dot; also `data-status="connected|reconnecting|disconnected"` |
| `header-total-value` | Header total portfolio value; text contains a `$` amount |
| `header-cash-balance` | Header cash balance; text contains a `$` amount |
| `watchlist` | Watchlist panel container |
| `watchlist-row-{TICKER}` | One row per watched ticker, e.g. `watchlist-row-AAPL` |
| `watchlist-price-{TICKER}` | Price cell text, e.g. `190.50` (with or without `$`) |
| `watchlist-change-{TICKER}` | Day change % cell |
| `watchlist-sparkline-{TICKER}` | Sparkline svg/canvas element |
| `watchlist-remove-{TICKER}` | Remove button on the row |
| `watchlist-add-input` | Text input for a new ticker |
| `watchlist-add-button` | Submit button for adding a ticker |
| `watchlist-error` | Inline error message (only rendered when there is one) |
| `main-chart` | Selected-ticker chart container |
| `main-chart-ticker` | Element whose text is the selected ticker symbol |
| `portfolio-heatmap` | Treemap container |
| `heatmap-tile-{TICKER}` | One tile per position |
| `pnl-chart` | Portfolio value line chart container |
| `positions-table` | Positions table container |
| `positions-empty` | Empty-state element (only when there are no positions) |
| `position-row-{TICKER}` | One row per position |
| `position-quantity-{TICKER}` | Quantity cell |
| `position-avgcost-{TICKER}` | Average cost cell |
| `position-price-{TICKER}` | Current price cell |
| `position-pnl-{TICKER}` | Unrealized P&L cell |
| `position-pnlpct-{TICKER}` | Unrealized P&L % cell |
| `trade-ticker-input` | Trade bar ticker input |
| `trade-quantity-input` | Trade bar quantity input |
| `trade-buy-button` | Buy button |
| `trade-sell-button` | Sell button |
| `trade-error` | Trade error banner (only when there is one) |
| `trade-success` | Trade confirmation banner (only when there is one) |
| `chat-panel` | Chat sidebar container |
| `chat-toggle` | Button that collapses/expands the chat panel |
| `chat-input` | Chat message input |
| `chat-send` | Chat send button |
| `chat-messages` | Scrolling message list container |
| `chat-message-user` | Each user message bubble (multiple) |
| `chat-message-assistant` | Each assistant message bubble (multiple) |
| `chat-loading` | Loading indicator (only while awaiting a response) |
| `chat-action` | Each inline action confirmation chip; also `data-status="executed|failed"` |

After any mutation (trade, watchlist add/remove, chat turn) the frontend refetches
`/api/portfolio` and `/api/watchlist` so the header, positions, heatmap and P&L chart converge
within one tick. The Integration Tester may assume convergence within 5 s.

---

## 7. Environment Variables

```bash
OPENROUTER_API_KEY=      # required for real LLM; unused when LLM_MOCK=true
MASSIVE_API_KEY=         # optional; empty -> GBM simulator
LLM_MOCK=false           # "true" -> deterministic mock LLM (E2E + no-key dev)
FINALLY_DB_PATH=         # optional override; Docker sets /app/db/finally.db
PORT=8000                # uvicorn port
```
`LLM_MOCK` is truthy for `"true"/"1"/"yes"` case-insensitively. The backend loads the project-root
`.env` via `python-dotenv` at startup (`load_dotenv()`), never overriding real environment variables.

---

## 8. Definition of Done (every team member)

1. Your code runs: `cd backend && uv run --extra dev pytest -q` is green (backend roles), or
   `cd frontend && npm run build && npm test` is green (frontend).
2. `cd backend && uv run --extra dev ruff check app tests` is clean (backend roles).
3. Unit tests cover your happy paths **and** your error paths.
4. You did not edit files outside your ownership boundary.
5. You appended your status to `planning/STATUS.md`.
