import type { FullConfig } from "@playwright/test";

const STARTING_CASH = 10_000;

async function get(url: string): Promise<Response> {
  return fetch(url, { headers: { accept: "application/json" } });
}

/**
 * Waits for the container to answer, then refuses to run against a book that has
 * already been traded — the fresh-start spec asserts an exact $10,000.00 balance and
 * an empty positions table, which only holds on a freshly started container.
 */
async function globalSetup(config: FullConfig): Promise<void> {
  const baseURL =
    (config.projects[0]?.use?.baseURL as string | undefined) ??
    process.env.E2E_BASE_URL ??
    "http://localhost:8000";

  const deadline = Date.now() + 90_000;
  let health: Record<string, unknown> | null = null;
  let lastError = "";

  while (Date.now() < deadline) {
    try {
      const res = await get(`${baseURL}/api/health`);
      if (res.ok) {
        health = (await res.json()) as Record<string, unknown>;
        break;
      }
      lastError = `HTTP ${res.status}`;
    } catch (err) {
      lastError = err instanceof Error ? err.message : String(err);
    }
    await new Promise((r) => setTimeout(r, 1_000));
  }

  if (!health) {
    throw new Error(
      `FinAlly is not reachable at ${baseURL} (last error: ${lastError}).\n` +
        `Start it first:\n` +
        `  docker compose -f test/docker-compose.test.yml up -d --build --force-recreate --wait finally-test`,
    );
  }

  if (health.llm_mock !== true) {
    throw new Error(
      `The app under test must run with LLM_MOCK=true so the chat specs are free and ` +
        `deterministic. /api/health reported llm_mock=${JSON.stringify(health.llm_mock)}.`,
    );
  }

  const portfolio = (await (await get(`${baseURL}/api/portfolio`)).json()) as {
    cash_balance: number;
    positions: unknown[];
  };

  const pristine =
    Math.abs(portfolio.cash_balance - STARTING_CASH) < 0.005 && portfolio.positions.length === 0;

  if (!pristine) {
    throw new Error(
      `The app under test is not on a fresh database ` +
        `(cash=$${portfolio.cash_balance.toFixed(2)}, positions=${portfolio.positions.length}). ` +
        `The suite asserts the seeded $10,000 / empty book, so recreate the container:\n` +
        `  docker compose -f test/docker-compose.test.yml up -d --force-recreate --wait finally-test`,
    );
  }

  // eslint-disable-next-line no-console
  console.log(
    `[global-setup] ${baseURL} ready — market data: ${health.market_data_source}, ` +
      `tickers tracked: ${health.tickers_tracked}, llm_mock: true, book: pristine.`,
  );
}

export default globalSetup;
