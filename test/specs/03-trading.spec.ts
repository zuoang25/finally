import { expect, test } from "@playwright/test";
import {
  fillPriceFromBanner,
  openTerminal,
  readBook,
  submitOrder,
  parseMoney,
} from "../utils/terminal";

/**
 * PLAN.md section 12: buy, sell, and the two validation errors.
 *
 * Serial: each test hands the next one a specific book state (3 AAPL -> 2 AAPL -> flat).
 * Every assertion is directional or an invariant — prices move every ~500 ms, so no
 * absolute price or total is ever asserted.
 */
test.describe.configure({ mode: "serial" });

test.describe("trading", () => {
  test.beforeEach(async ({ page }) => {
    await openTerminal(page);
  });

  test("a buy debits cash, opens a position and shows it in the table and heatmap", async ({
    page,
  }) => {
    const before = await readBook(page);
    expect(before.cash).toBeGreaterThan(0);

    await submitOrder(page, "buy", "AAPL", "3");

    await expect(page.getByTestId("trade-success")).toBeVisible();
    await expect(page.getByTestId("trade-error")).toHaveCount(0);
    const fill = await fillPriceFromBanner(page);
    expect(fill).toBeGreaterThan(0);

    await expect(page.getByTestId("position-row-AAPL")).toBeVisible();
    await expect(page.getByTestId("position-quantity-AAPL")).toHaveText("3");
    await expect(page.getByTestId("positions-empty")).toHaveCount(0);
    await expect(page.getByTestId("heatmap-tile-AAPL")).toBeVisible();

    // Average cost is the fill price on a first buy (CONTRACTS.md section 3.7).
    expect(parseMoney(await page.getByTestId("position-avgcost-AAPL").textContent())).toBeCloseTo(
      fill,
      2,
    );

    // Cash falls by quantity x fill price. Poll: the header refetches after the trade.
    await expect
      .poll(async () => (await readBook(page)).cash, { message: "cash never fell after the buy" })
      .toBeLessThan(before.cash);

    const after = await readBook(page, ["AAPL"]);
    expect(after.cash).toBeCloseTo(before.cash - 3 * fill, 2);

    // Header total is cash plus the live mark of the book, read in the same frame.
    expect(after.total).toBeCloseTo(after.cash + 3 * after.positions.AAPL.price, 1);
  });

  test("a partial sell credits cash and shrinks the position", async ({ page }) => {
    await expect(page.getByTestId("position-quantity-AAPL")).toHaveText("3");
    const before = await readBook(page, ["AAPL"]);

    await submitOrder(page, "sell", "AAPL", "1");

    await expect(page.getByTestId("trade-success")).toBeVisible();
    const fill = await fillPriceFromBanner(page);

    await expect(page.getByTestId("position-quantity-AAPL")).toHaveText("2");
    await expect(page.getByTestId("position-row-AAPL")).toBeVisible();

    await expect
      .poll(async () => (await readBook(page)).cash, { message: "cash never rose after the sell" })
      .toBeGreaterThan(before.cash);

    const after = await readBook(page, ["AAPL"]);
    expect(after.cash).toBeCloseTo(before.cash + fill, 2);
    // A sell leaves average cost untouched (CONTRACTS.md section 3.7).
    expect(after.positions.AAPL.avgCost).toBeCloseTo(before.positions.AAPL.avgCost, 2);
    expect(after.total).toBeCloseTo(after.cash + 2 * after.positions.AAPL.price, 1);
  });

  test("selling the rest closes the position and empties the table", async ({ page }) => {
    await expect(page.getByTestId("position-quantity-AAPL")).toHaveText("2");

    await submitOrder(page, "sell", "AAPL", "2");

    await expect(page.getByTestId("trade-success")).toBeVisible();
    await expect(page.getByTestId("position-row-AAPL")).toHaveCount(0);
    await expect(page.getByTestId("heatmap-tile-AAPL")).toHaveCount(0);
    await expect(page.getByTestId("positions-empty")).toBeVisible();

    const after = await readBook(page);
    expect(after.total).toBeCloseTo(after.cash, 2);
  });

  test("a buy larger than the cash balance is rejected and surfaced in the UI", async ({ page }) => {
    const before = await readBook(page);

    await submitOrder(page, "buy", "AAPL", "100000");

    await expect(page.getByTestId("trade-error")).toBeVisible();
    await expect(page.getByTestId("trade-error")).toContainText(/insufficient/i);
    await expect(page.getByTestId("trade-success")).toHaveCount(0);
    await expect(page.getByTestId("position-row-AAPL")).toHaveCount(0);

    const after = await readBook(page);
    expect(after.cash).toBeCloseTo(before.cash, 2);
  });

  test("selling shares that are not held is rejected and surfaced in the UI", async ({ page }) => {
    const before = await readBook(page);

    await submitOrder(page, "sell", "TSLA", "5");

    await expect(page.getByTestId("trade-error")).toBeVisible();
    await expect(page.getByTestId("trade-error")).toContainText(/insufficient/i);
    await expect(page.getByTestId("position-row-TSLA")).toHaveCount(0);

    const after = await readBook(page);
    expect(after.cash).toBeCloseTo(before.cash, 2);
  });

  test("client-side validation blocks an empty or non-positive quantity", async ({ page }) => {
    await submitOrder(page, "buy", "AAPL", "0");
    await expect(page.getByTestId("trade-error")).toBeVisible();
    await expect(page.getByTestId("positions-empty")).toBeVisible();
  });
});
