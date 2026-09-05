import { expect, test } from "@playwright/test";
import { flattenBook, openTerminal, parseMoney, readBook, submitOrder } from "../utils/terminal";

/**
 * PLAN.md section 12: "Portfolio visualisation: heatmap renders with correct colours,
 * P&L chart has data points."
 *
 * The charts are TradingView Lightweight Charts drawing into a <canvas> inside the
 * `main-chart` / `pnl-chart` containers, and both containers render explanatory copy
 * until they hold two points. Asserting the canvas exists inside the contract testid is
 * therefore the "has data" check; the container alone proves nothing.
 */
test.describe.configure({ mode: "serial" });

test.describe("visualisations", () => {
  test.beforeEach(async ({ page }) => {
    await openTerminal(page);
  });

  test.afterAll(async ({ browser }) => {
    const page = await browser.newPage();
    await openTerminal(page);
    await flattenBook(page);
    await page.close();
  });

  test("the heatmap renders one tile per position, sized by weight", async ({ page }) => {
    await submitOrder(page, "buy", "NVDA", "4");
    await expect(page.getByTestId("trade-success")).toBeVisible();
    await submitOrder(page, "buy", "MSFT", "2");
    await expect(page.getByTestId("trade-success")).toBeVisible();

    await expect(page.getByTestId("heatmap-tile-NVDA")).toBeVisible();
    await expect(page.getByTestId("heatmap-tile-MSFT")).toBeVisible();
    await expect(page.locator("[data-testid^='heatmap-tile-']")).toHaveCount(2);

    // Sized by portfolio weight: the larger market value gets the larger tile.
    const book = await readBook(page, ["NVDA", "MSFT"]);
    const areas = await page.evaluate(() =>
      Object.fromEntries(
        Array.from(document.querySelectorAll("[data-testid^='heatmap-tile-']")).map((el) => {
          const box = el.getBoundingClientRect();
          return [
            (el.getAttribute("data-testid") ?? "").replace("heatmap-tile-", ""),
            box.width * box.height,
          ];
        }),
      ),
    );
    const nvdaValue = 4 * book.positions.NVDA.price;
    const msftValue = 2 * book.positions.MSFT.price;
    if (nvdaValue > msftValue) {
      expect(areas.NVDA).toBeGreaterThan(areas.MSFT);
    } else {
      expect(areas.MSFT).toBeGreaterThan(areas.NVDA);
    }
  });

  test("the positions table shows quantity, average cost, live price and P&L", async ({ page }) => {
    await expect(page.getByTestId("positions-table")).toBeVisible();
    await expect(page.getByTestId("position-quantity-NVDA")).toHaveText("4");
    await expect(page.getByTestId("position-quantity-MSFT")).toHaveText("2");

    for (const ticker of ["NVDA", "MSFT"]) {
      await expect
        .poll(async () =>
          parseMoney(await page.getByTestId(`position-price-${ticker}`).textContent()),
        )
        .toBeGreaterThan(0);
      await expect
        .poll(async () =>
          parseMoney(await page.getByTestId(`position-avgcost-${ticker}`).textContent()),
        )
        .toBeGreaterThan(0);
      await expect(page.getByTestId(`position-pnl-${ticker}`)).toBeVisible();
      await expect(page.getByTestId(`position-pnlpct-${ticker}`)).toBeVisible();
    }

    // Unrealized P&L is quantity x (live price - average cost), read in one frame.
    const book = await readBook(page, ["NVDA"]);
    const nvda = book.positions.NVDA;
    expect(nvda.pnl).toBeCloseTo(4 * (nvda.price - nvda.avgCost), 1);
  });

  test("the P&L chart draws a curve from the portfolio snapshots", async ({ page }) => {
    // Boot snapshot + post-trade snapshots + the live total give it well over two points.
    await expect(page.getByTestId("pnl-chart")).toBeVisible();
    await expect(page.getByTestId("pnl-chart").locator("canvas").first()).toBeVisible({
      timeout: 30_000,
    });
  });

  test("the main chart follows the selected ticker and draws the streamed trace", async ({
    page,
  }) => {
    await page.getByTestId("watchlist-row-NVDA").click();
    await expect(page.getByTestId("main-chart-ticker")).toHaveText("NVDA");

    // The trace accumulates from SSE since page load, so allow a couple of ticks.
    await expect(page.getByTestId("main-chart").locator("canvas").first()).toBeVisible({
      timeout: 30_000,
    });

    // Selecting from the heatmap drives the same chart.
    await page.getByTestId("heatmap-tile-MSFT").click();
    await expect(page.getByTestId("main-chart-ticker")).toHaveText("MSFT");
  });
});
