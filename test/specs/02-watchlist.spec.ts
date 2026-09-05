import { expect, test } from "@playwright/test";
import { DEFAULT_TICKERS, openTerminal, parseMoney, readWatchlistTickers } from "../utils/terminal";

/**
 * PLAN.md section 12: "Add and remove a ticker from the watchlist."
 *
 * NFLX is used as the moving part: it is seeded (so the mock LLM and the simulator both
 * know it) and it is last in `added_at` order, so removing and re-adding it leaves the
 * rest of the list untouched for later specs.
 */
test.describe("watchlist", () => {
  test.beforeEach(async ({ page }) => {
    await openTerminal(page);
  });

  test("removes a ticker and then adds it back, with prices resuming", async ({ page }) => {
    const row = page.getByTestId("watchlist-row-NFLX");
    await expect(row).toBeVisible();

    await page.getByTestId("watchlist-remove-NFLX").click();
    await expect(row).toHaveCount(0);
    await expect(page.getByTestId("watchlist-price-NFLX")).toHaveCount(0);
    expect(await readWatchlistTickers(page)).toEqual(
      DEFAULT_TICKERS.filter((t) => t !== "NFLX"),
    );

    // Lower case on purpose: CONTRACTS.md section 4.3 upper-cases server-side.
    await page.getByTestId("watchlist-add-input").fill("nflx");
    await page.getByTestId("watchlist-add-button").click();

    await expect(row).toBeVisible();
    await expect(page.getByTestId("watchlist-add-input")).toHaveValue("");
    await expect(page.getByTestId("watchlist-error")).toHaveCount(0);

    // A newly added ticker has no price until the next tick — it must arrive.
    await expect
      .poll(async () => parseMoney(await page.getByTestId("watchlist-price-NFLX").textContent()), {
        message: "NFLX never started streaming again after being re-added",
        timeout: 30_000,
      })
      .toBeGreaterThan(0);

    expect(await readWatchlistTickers(page)).toHaveLength(DEFAULT_TICKERS.length);
  });

  test("surfaces the server's rejection when the ticker is already watched", async ({ page }) => {
    await page.getByTestId("watchlist-add-input").fill("AAPL");
    await page.getByTestId("watchlist-add-button").click();

    // CONTRACTS.md section 4.3: duplicate add -> 409, message surfaced inline.
    await expect(page.getByTestId("watchlist-error")).toBeVisible();
    await expect(page.getByTestId("watchlist-error")).toContainText("AAPL");
    expect(await readWatchlistTickers(page)).toHaveLength(DEFAULT_TICKERS.length);
  });

  test("rejects a malformed symbol without adding a row", async ({ page }) => {
    await page.getByTestId("watchlist-add-input").fill("12345");
    await page.getByTestId("watchlist-add-button").click();

    await expect(page.getByTestId("watchlist-error")).toBeVisible();
    expect(await readWatchlistTickers(page)).toEqual([...DEFAULT_TICKERS]);
  });

  test("clicking a row drives the main chart selection", async ({ page }) => {
    await page.getByTestId("watchlist-row-TSLA").click();
    await expect(page.getByTestId("main-chart-ticker")).toHaveText("TSLA");
    // The trade bar mirrors the selection so a click pre-fills the order.
    await expect(page.getByTestId("trade-ticker-input")).toHaveValue("TSLA");
  });
});
