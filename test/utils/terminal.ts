import { expect, type Locator, type Page } from "@playwright/test";

/**
 * Every selector in this suite goes through this module or through
 * `page.getByTestId(...)`, so the whole surface stays inside the frozen
 * CONTRACTS.md section 6.1 testid list — no CSS classes, no visible-text lookups.
 */

/** CONTRACTS.md / PLAN.md section 7 seed watchlist, in `added_at` order. */
export const DEFAULT_TICKERS = [
  "AAPL",
  "GOOGL",
  "MSFT",
  "AMZN",
  "TSLA",
  "NVDA",
  "META",
  "JPM",
  "V",
  "NFLX",
] as const;

export const STARTING_CASH = 10_000;

/** `"$10,000.00"` -> `10000`, `"-$12.30"` -> `-12.3`, `"—"` -> `NaN`. */
export function parseMoney(text: string | null | undefined): number {
  if (!text) return Number.NaN;
  const cleaned = text.replace(/[^0-9.-]/g, "");
  if (cleaned === "" || cleaned === "-" || cleaned === ".") return Number.NaN;
  return Number(cleaned);
}

/** Loads `/`, waits for hydration, the first portfolio fetch and the SSE stream. */
export async function openTerminal(page: Page): Promise<void> {
  await page.goto("/");
  await expect(page.getByTestId("app-root")).toBeVisible();
  // The header shows an em dash until /api/portfolio lands.
  await expect
    .poll(async () => parseMoney(await page.getByTestId("header-cash-balance").textContent()), {
      message: "header cash balance never resolved to a number",
      timeout: 30_000,
    })
    .not.toBeNaN();
  await expect(page.getByTestId("connection-status")).toHaveAttribute("data-status", "connected", {
    timeout: 30_000,
  });
}

/**
 * One atomic DOM read of the header, so `total`, `cash` and the position cells all
 * come from the same paint. Prices tick every ~500 ms, so reading them with separate
 * locator calls would compare numbers from different frames.
 */
export async function readBook(
  page: Page,
  tickers: string[] = [],
): Promise<{
  total: number;
  cash: number;
  positions: Record<string, { quantity: number; avgCost: number; price: number; pnl: number }>;
}> {
  const raw = await page.evaluate((syms) => {
    const text = (id: string) =>
      document.querySelector(`[data-testid="${id}"]`)?.textContent?.trim() ?? null;
    const positions: Record<string, Record<string, string | null>> = {};
    for (const sym of syms) {
      if (!document.querySelector(`[data-testid="position-row-${sym}"]`)) continue;
      positions[sym] = {
        quantity: text(`position-quantity-${sym}`),
        avgCost: text(`position-avgcost-${sym}`),
        price: text(`position-price-${sym}`),
        pnl: text(`position-pnl-${sym}`),
      };
    }
    return { total: text("header-total-value"), cash: text("header-cash-balance"), positions };
  }, tickers);

  const positions: Record<
    string,
    { quantity: number; avgCost: number; price: number; pnl: number }
  > = {};
  for (const [sym, cells] of Object.entries(raw.positions)) {
    positions[sym] = {
      quantity: parseMoney(cells.quantity),
      avgCost: parseMoney(cells.avgCost),
      price: parseMoney(cells.price),
      pnl: parseMoney(cells.pnl),
    };
  }
  return { total: parseMoney(raw.total), cash: parseMoney(raw.cash), positions };
}

/** Snapshot of every rendered `watchlist-price-{TICKER}` cell, keyed by ticker. */
export async function readWatchlistPrices(page: Page): Promise<Record<string, string>> {
  return page.evaluate(() => {
    const out: Record<string, string> = {};
    for (const el of Array.from(document.querySelectorAll("[data-testid^='watchlist-price-']"))) {
      const id = el.getAttribute("data-testid") ?? "";
      out[id.replace("watchlist-price-", "")] = (el.textContent ?? "").trim();
    }
    return out;
  });
}

/** The tickers currently rendered in the watchlist, in DOM order. */
export async function readWatchlistTickers(page: Page): Promise<string[]> {
  return page.evaluate(() =>
    Array.from(document.querySelectorAll("[data-testid^='watchlist-row-']")).map((el) =>
      (el.getAttribute("data-testid") ?? "").replace("watchlist-row-", ""),
    ),
  );
}

/** Waits until at least one streamed price actually moves. */
export async function expectPricesToTick(page: Page, timeout = 30_000): Promise<void> {
  const before = await readWatchlistPrices(page);
  await expect
    .poll(
      async () => {
        const now = await readWatchlistPrices(page);
        return Object.entries(now).filter(([t, v]) => before[t] !== undefined && before[t] !== v)
          .length;
      },
      { message: "no watchlist price changed — the SSE stream is not ticking", timeout },
    )
    .toBeGreaterThan(0);
}

/** Submits a market order through the trade bar and waits for it to settle. */
export async function submitOrder(
  page: Page,
  side: "buy" | "sell",
  ticker: string,
  quantity: string,
): Promise<void> {
  await page.getByTestId("trade-ticker-input").fill(ticker);
  await page.getByTestId("trade-quantity-input").fill(quantity);
  const button = page.getByTestId(side === "buy" ? "trade-buy-button" : "trade-sell-button");
  await button.click();
  await expect(button).toBeEnabled();
}

/** Fill price out of the `trade-success` banner, e.g. "Bought 3 AAPL at 190.50". */
export async function fillPriceFromBanner(page: Page): Promise<number> {
  const banner = page.getByTestId("trade-success");
  await expect(banner).toBeVisible();
  const text = (await banner.textContent()) ?? "";
  const match = text.match(/at\s+([\d,]+\.\d+)\s*$/);
  expect(match, `could not read a fill price out of trade-success: "${text}"`).not.toBeNull();
  return parseMoney(match![1]);
}

/** Sends a chat message and resolves once a new assistant bubble has rendered. */
export async function sendChat(page: Page, message: string): Promise<Locator> {
  const assistants = page.getByTestId("chat-message-assistant");
  const before = await assistants.count();
  await page.getByTestId("chat-input").fill(message);
  await page.getByTestId("chat-send").click();
  // LLM_MOCK=true answers in milliseconds, so wait for the bubble, never the spinner.
  await expect(assistants).toHaveCount(before + 1, { timeout: 30_000 });
  return assistants.nth(before);
}

/** Closes out every open position through the trade bar, leaving an empty book. */
export async function flattenBook(page: Page): Promise<void> {
  for (let guard = 0; guard < 12; guard += 1) {
    const rows = await page.evaluate(() =>
      Array.from(document.querySelectorAll("[data-testid^='position-row-']")).map((el) => {
        const ticker = (el.getAttribute("data-testid") ?? "").replace("position-row-", "");
        const qty =
          document
            .querySelector(`[data-testid="position-quantity-${ticker}"]`)
            ?.textContent?.trim() ?? "0";
        return { ticker, qty };
      }),
    );
    if (rows.length === 0) return;
    for (const row of rows) {
      await submitOrder(page, "sell", row.ticker, row.qty.replace(/,/g, ""));
      await expect(page.getByTestId(`position-row-${row.ticker}`)).toHaveCount(0);
    }
  }
  await expect(page.getByTestId("positions-empty")).toBeVisible();
}
