import { expect, test } from "@playwright/test";
import { flattenBook, openTerminal, readBook, sendChat } from "../utils/terminal";

/**
 * PLAN.md section 12: "AI chat (mocked): send a message, receive a response, trade
 * execution appears inline."
 *
 * The app under test runs with LLM_MOCK=true (enforced in global-setup.ts), so every
 * reply here comes from the deterministic table in CONTRACTS.md section 5.3 and no
 * OpenRouter call is ever made. Mock replies still flow through the real execution
 * path, so the portfolio really does move.
 */
test.describe.configure({ mode: "serial" });

test.describe("AI chat", () => {
  test.beforeEach(async ({ page }) => {
    await openTerminal(page);
  });

  test.afterAll(async ({ browser }) => {
    const page = await browser.newPage();
    await openTerminal(page);
    await flattenBook(page);
    await page.close();
  });

  test("collapses and reopens from the header toggle", async ({ page }) => {
    const panel = page.getByTestId("chat-panel");
    await expect(panel).toBeVisible();

    await page.getByTestId("chat-toggle").click();
    await expect(panel).not.toBeVisible();

    await page.getByTestId("chat-toggle").click();
    await expect(panel).toBeVisible();
  });

  test("answers a conversational question without touching the book", async ({ page }) => {
    const before = await readBook(page);

    const reply = await sendChat(page, "how am I doing today?");

    await expect(page.getByTestId("chat-message-user")).toHaveCount(1);
    await expect(reply).toContainText("MOCK:");
    await expect(page.getByTestId("chat-action")).toHaveCount(0);

    const after = await readBook(page);
    expect(after.cash).toBeCloseTo(before.cash, 2);
    await expect(page.getByTestId("positions-empty")).toBeVisible();
  });

  test("executes a buy and shows it inline, reflected in the portfolio", async ({ page }) => {
    const before = await readBook(page);

    const reply = await sendChat(page, "buy 3 NVDA");

    await expect(reply).toContainText("Executed: bought");

    const chip = page.getByTestId("chat-action").last();
    await expect(chip).toBeVisible();
    await expect(chip).toHaveAttribute("data-status", "executed");
    await expect(chip).toContainText("NVDA");

    // The chat turn refreshes the terminal, so the trade lands everywhere.
    await expect(page.getByTestId("position-row-NVDA")).toBeVisible();
    await expect(page.getByTestId("position-quantity-NVDA")).toHaveText("3");
    await expect(page.getByTestId("heatmap-tile-NVDA")).toBeVisible();
    await expect
      .poll(async () => (await readBook(page)).cash, { message: "cash never fell after a chat buy" })
      .toBeLessThan(before.cash);
  });

  test("executes a sell that closes the position", async ({ page }) => {
    await expect(page.getByTestId("position-quantity-NVDA")).toHaveText("3");
    const before = await readBook(page);

    const reply = await sendChat(page, "sell 3 NVDA");

    await expect(reply).toContainText("Executed: sold");
    await expect(page.getByTestId("chat-action").last()).toHaveAttribute("data-status", "executed");
    await expect(page.getByTestId("position-row-NVDA")).toHaveCount(0);
    await expect(page.getByTestId("positions-empty")).toBeVisible();
    await expect
      .poll(async () => (await readBook(page)).cash, {
        message: "cash never rose after a chat sell",
      })
      .toBeGreaterThan(before.cash);
  });

  test("reports a trade it could not execute as a failed action chip", async ({ page }) => {
    const before = await readBook(page);

    const reply = await sendChat(page, "buy 100000 AAPL");

    const chip = page.getByTestId("chat-action").last();
    await expect(chip).toHaveAttribute("data-status", "failed");
    await expect(reply).toContainText("Could not complete");
    await expect(page.getByTestId("position-row-AAPL")).toHaveCount(0);

    const after = await readBook(page);
    expect(after.cash).toBeCloseTo(before.cash, 2);
  });

  test("removes and re-adds a watchlist ticker on request", async ({ page }) => {
    await expect(page.getByTestId("watchlist-row-NFLX")).toBeVisible();

    const removal = await sendChat(page, "remove NFLX from my watchlist");
    await expect(removal).toContainText("Removed");
    await expect(page.getByTestId("chat-action").last()).toHaveAttribute("data-status", "executed");
    await expect(page.getByTestId("watchlist-row-NFLX")).toHaveCount(0);

    const addition = await sendChat(page, "add NFLX to my watchlist");
    await expect(addition).toContainText("Added");
    await expect(page.getByTestId("chat-action").last()).toHaveAttribute("data-status", "executed");
    await expect(page.getByTestId("watchlist-row-NFLX")).toBeVisible();
  });

  test("keeps the conversation after a reload", async ({ page }) => {
    // Every turn above is persisted; /api/chat/history rehydrates the panel.
    await expect(page.getByTestId("chat-messages")).toBeVisible();
    await expect(page.getByTestId("chat-message-user").first()).toBeVisible();
    await expect(page.getByTestId("chat-message-assistant").first()).toBeVisible();
    const users = await page.getByTestId("chat-message-user").count();
    expect(users).toBeGreaterThanOrEqual(5);
  });
});
