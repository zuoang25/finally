# FinAlly — AI Trading Workstation

A visually stunning AI-powered trading workstation that streams live market data, simulates portfolio trading, and integrates an LLM chat assistant that can analyze positions and execute trades via natural language.

Built entirely by coding agents as a capstone project for an agentic AI coding course.

## Features

- **Live price streaming** via SSE with green/red flash animations
- **Simulated portfolio** — $10k virtual cash, market orders, instant fills
- **Portfolio visualizations** — heatmap (treemap), P&L chart, positions table
- **AI chat assistant** — analyzes holdings, suggests and auto-executes trades
- **Watchlist management** — track tickers manually or via AI
- **Dark terminal aesthetic** — Bloomberg-inspired, data-dense layout

## Architecture

Single Docker container serving everything on port 8000:

- **Frontend**: Next.js (static export) with TypeScript and Tailwind CSS
- **Backend**: FastAPI (Python/uv) with SSE streaming
- **Database**: SQLite with lazy initialization
- **AI**: LiteLLM → OpenRouter (Cerebras inference) with structured outputs
- **Market data**: Built-in GBM simulator (default) or Massive API (optional)

## Quick Start

```bash
# Clone and configure
cp .env.example .env
# Add your OPENROUTER_API_KEY to .env

# Start it (builds the image on first run)
./scripts/start_mac.sh              # macOS / Linux
pwsh scripts/start_windows.ps1      # Windows

# Open http://localhost:8000
```

To stop it (the data volume is preserved):

```bash
./scripts/stop_mac.sh               # macOS / Linux
pwsh scripts/stop_windows.ps1       # Windows
```

Or drive Docker directly:

```bash
docker build -t finally .
docker run -v finally-data:/app/db -p 8000:8000 --env-file .env finally
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key for AI chat |
| `MASSIVE_API_KEY` | No | Massive (Polygon.io) key for real market data; omit to use simulator |
| `LLM_MOCK` | No | Set `true` for deterministic mock LLM responses (testing) |
| `FINALLY_DB_PATH` | No | Override the SQLite path; the container sets `/app/db/finally.db` |

Without `OPENROUTER_API_KEY` everything works except live AI chat. Without `MASSIVE_API_KEY` the
built-in GBM simulator drives prices, which is the recommended default.

## Project Structure

```
finally/
├── frontend/    # Next.js static export
├── backend/     # FastAPI uv project
├── planning/    # Project documentation and agent contracts
├── test/        # Playwright E2E tests
├── db/          # SQLite volume mount (runtime)
└── scripts/     # Start/stop helpers
```

## Testing

```bash
cd backend && uv run --extra dev pytest -q     # 328 unit/integration tests
cd frontend && npm test -- --run               # 107 component tests
cd test && npm run e2e                         # 27 Playwright E2E tests
```

The E2E suite builds the production image and runs against it with `LLM_MOCK=true`, so it needs no
API key. It defaults to host port **8100** and mounts no volume at all - the database lives in a
tmpfs and is reseeded on every start - so it can run alongside a live app on 8000 without
interfering with it or with your `finally-data` volume. Override the port with `E2E_HOST_PORT` if
8100 is taken.

## Documentation

- `planning/BUILD_SUMMARY.md` - what was built, key decisions, and gotchas (start here)
- `planning/CONTRACTS.md` - the authoritative interface contract between components
- `planning/PLAN.md` - the original specification

## License

See [LICENSE](LICENSE).
