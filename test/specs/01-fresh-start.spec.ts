import { expect, test } from "@playwright/test";
import {
  DEFAULT_TICKERS,
  STARTING_CASH,
  expectPricesToTick,
  openTerminal,
  parseMoney,
  readBook,
  readWatchlistTickers,
} from "../utils/terminal";

/**
 * PLAN.md section 12: "Fresh start: default watchlist appears, $10k balance shown,
 * prices are streaming." Runs first, against the pristine database that
 * global-setup.ts has already verified.
 */
test.describe("fresh start", () => {
  test.beforeEach(async ({ page }) => {
    await openTerminal(page);
  });

  test("shows the ten seeded tickers, each with a price, a day change and a sparkline", async ({
    page,
  }) => {
    expect(await readWatchlistTickers(page)).toEqual([...DEFAULT_TICKERS]);

    for (const ticker of DEFAULT_TICKERS) {
      await expect(page.getByTestId(`watchlist-row-${ticker}`)).toBeVisible();
      await expect(page.getByTestId(`watchlist-sparkline-${ticker}`)).toBeAttached();
      await expect(page.getByTestId(`watchlist-change-${ticker}`)).toBeVisible();

      // The simulator seeds a price for every default ticker, so no cell should be a dash.
      await expect
        .poll(async () => parseMoney(await page.getByTestId(`watchlist-price-${ticker}`).textContent()), {
          message: `${ticker} never rendered a numeric price`,
        })
        .toBeGreaterThan(0);
    }
  });

  test("starts with $10,000 in cash, no positions and a total equal to cash", async ({ page }) => {
    const book = await readBook(page);
    expect(book.cash).toBeCloseTo(STARTING_CASH, 2);
    expect(book.total).toBeCloseTo(STARTING_CASH, 2);

    await expect(page.getByTestId("positions-table")).toBeVisible();
    await expect(page.getByTestId("positions-empty")).toBeVisible();
    await expect(page.getByTestId("portfolio-heatmap")).toBeVisible();
    await expect(page.locator("[data-testid^='heatmap-tile-']")).toHaveCount(0);
  });

  test("streams live prices and reports a connected feed", async ({ page }) => {
    await expect(page.getByTestId("connection-status")).toHaveAttribute("data-status", "connected");
    await expectPricesToTick(page);
  });

  test("renders every terminal panel and selects the first ticker by default", async ({ page }) => {
    await expect(page.getByTestId("watchlist")).toBeVisible();
    await expect(page.getByTestId("main-chart")).toBeVisible();
    await expect(page.getByTestId("pnl-chart")).toBeVisible();
    await expect(page.getByTestId("chat-panel")).toBeVisible();
    await expect(page.getByTestId("chat-messages")).toBeVisible();
    await expect(page.getByTestId("main-chart-ticker")).toHaveText(DEFAULT_TICKERS[0]);

    // Nothing has gone wrong yet, so none of the transient banners should exist.
    await expect(page.getByTestId("watchlist-error")).toHaveCount(0);
    await expect(page.getByTestId("trade-error")).toHaveCount(0);
    await expect(page.getByTestId("trade-success")).toHaveCount(0);
  });
});
