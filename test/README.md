# FinAlly — end-to-end tests

Playwright suite that drives the **real production container** (built from the repo's
`Dockerfile`, unmodified) through a Chromium browser. It is the last gate before shipping:
backend unit tests prove the API, frontend unit tests prove the components, and this proves
they are actually wired together.

## Run it

From the repo root, everything in one step:

```bash
cd test
npm install                 # first time only
npx playwright install chromium   # first time only
npm run e2e                 # builds + starts the app container, then runs the suite
```

`npm run e2e` is `npm run app:up && npm test`. The two halves separately:

```bash
npm run app:up      # docker compose up -d --build --force-recreate --wait finally-test
npm test            # playwright test
npm run app:down    # tear the stack down
npm run app:logs    # app container logs, if something looks wrong
npm run test:report # open the HTML report from the last run
```

The stack publishes on **host port 8100**, not 8000, on purpose: a developer's production
`finally` container routinely owns 8000 (and it picks up the real project-root `.env`, so it runs
with `llm_mock: false`). Inside the container the app still listens on 8000. To move it, set the
one variable both the compose file and the Playwright config read:

```bash
E2E_HOST_PORT=8200 npm run e2e
```

### Running the browser in a container instead

Browser dependencies are deliberately kept out of the production image (PLAN.md §12), so the
suite can also run from the official Playwright image on the compose network:

```bash
docker compose -f docker-compose.test.yml up -d --build --wait finally-test
docker compose -f docker-compose.test.yml run --rm playwright
```

That path installs `node_modules` inside the container and targets `http://finally-test:8000`.
It pulls a ~2 GB image the first time.

## What the app under test looks like

`docker-compose.test.yml` builds the production `Dockerfile` and runs it with:

| Setting | Value | Why |
|---|---|---|
| `LLM_MOCK` | `true` | Chat specs are free, instant and deterministic (CONTRACTS.md §5.3). **No OpenRouter call is ever made.** |
| `OPENROUTER_API_KEY` / `MASSIVE_API_KEY` | empty | No `env_file`, so the developer's real `.env` can never leak into a test run. Market data is the built-in GBM simulator. |
| `FINALLY_DB_PATH` | `/tmp/e2e/finally.db`, on a **tmpfs** | Every container start gets a pristine seeded database: $10,000 cash, empty book, the 10 default tickers. There is no volume of any kind on this service — the production `finally-data` volume is never mounted, so a previous run's trades cannot leak in. |
| published port | `8100` (host) → `8000` (container) | Never collides with a production `finally` container on 8000. |

`utils/global-setup.ts` refuses to start if the app is unreachable, if `llm_mock` is not `true`,
or if the book is not pristine — the fresh-start spec asserts an exact `$10,000.00`, so a dirty
database is a setup error, not a test failure. Recreate the container and run again:

```bash
docker compose -f docker-compose.test.yml up -d --force-recreate --wait finally-test
```

## Coverage

| Spec | Scenarios |
|---|---|
| `01-fresh-start` | The 10 seeded tickers with price, day change and sparkline; $10,000 cash, total = cash, empty positions and heatmap; feed `connected` and prices actually moving; every panel present; first ticker selected. |
| `02-watchlist` | Remove a ticker and see it (and its price cell) go; add it back lower-case and see prices resume; duplicate add surfaces the server's 409 inline; malformed symbol rejected; row click drives the main chart and pre-fills the order. |
| `03-trading` | Buy: cash debited by `quantity × fill`, position opens with `avg_cost == fill`, tile appears, header total ≈ cash + live mark. Partial sell: cash credited, quantity shrinks, `avg_cost` unchanged. Full sell: position and tile gone, empty state back. Insufficient cash, insufficient shares and a non-positive quantity all surface in `trade-error` and leave cash untouched. |
| `04-visualisations` | One heatmap tile per position, the bigger market value getting the bigger tile; positions table quantity/avg cost/live price/P&L with `pnl == qty × (price − avg cost)`; P&L chart draws its curve; main chart follows both watchlist and heatmap selection and draws the streamed trace. |
| `05-chat` | Panel collapses and reopens; a conversational turn answers without touching the book; "buy 3 NVDA" returns an `executed` action chip that really moves cash, positions and the heatmap; the matching sell closes it; an unaffordable buy comes back as a `failed` chip with cash unchanged; watchlist remove/add through chat; history survives a reload. |
| `06-sse-resilience` | Reload rebuilds the stream; severing the stream flips the header dot off `connected` and it recovers — with prices ticking again — with no reload and no user action. |

## House rules for this suite

- **Selectors are the frozen CONTRACTS.md §6.1 `data-testid` list, and nothing else.** No CSS
  classes, no visible-text lookups. The only structural exception is asserting that a `<canvas>`
  exists *inside* the `main-chart` / `pnl-chart` testids — those containers always render, so the
  canvas is the only proof the chart actually has data. Anything else that needs a handle is a
  Cross-Team Request to the Frontend Engineer, not a workaround here.
- **Nothing is asserted against a frozen price.** The simulator ticks every ~500 ms, so every
  money assertion is either directional (`cash went down`) or an invariant computed from the same
  paint (`total ≈ cash + qty × price`). `utils/terminal.ts#readBook` does one `page.evaluate` so
  the header and the position cells cannot come from different frames.
- **No fixed sleeps.** Convergence is `expect.poll` / web-first assertions throughout.
- **Do not assert on the `flash-up` / `flash-down` classes** — the flash lasts ~500 ms and the
  simulator ticks every ~500 ms, so it is inherently racy. Assert `watchlist-price-{TICKER}` text.
- **Do not wait for `chat-loading`** — under `LLM_MOCK=true` it can last milliseconds. Wait for
  the new `chat-message-assistant` bubble (`utils/terminal.ts#sendChat` does).
- **`chat-panel` collapses via the `hidden` attribute and stays mounted** — use
  `not.toBeVisible()`, never `toBeAttached()`.
- **Specs share one database**, so they run on a single worker in file-name order and each file
  restores the book it dirtied. Retries are off on purpose: a retry would replay trades against
  already-mutated state and could turn a real defect green.
- `06-sse-resilience` runs last because its forced disconnect bounces the app container, which
  (by design) resets the tmpfs database.

## Layout

```
test/
├── docker-compose.test.yml   app container + Playwright container
├── playwright.config.ts      single chromium project, 1 worker, no retries
├── specs/                    01..06, run in this order
└── utils/
    ├── global-setup.ts       reachability + LLM_MOCK + pristine-database gate
    ├── terminal.ts           every testid selector and the shared page helpers
    └── app-control.ts        forced SSE disconnect (docker CLI or /var/run/docker.sock)
```
