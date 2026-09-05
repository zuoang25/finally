import { expect, test } from "@playwright/test";
import { canRestartApp, restartAppContainer } from "../utils/app-control";
import { expectPricesToTick, openTerminal, readWatchlistPrices } from "../utils/terminal";

/**
 * PLAN.md section 12: "SSE resilience: disconnect and verify reconnection."
 *
 * Runs last on purpose: the forced disconnect bounces the app container, and the test
 * database lives in a tmpfs, so the book is reset to the seeded $10,000 afterwards.
 *
 * Note on method: `BrowserContext.setOffline()` was tried first and is NOT a valid
 * disconnect here — Chromium's offline emulation blocks new requests but leaves an
 * already-streaming response untouched, so the header dot stayed green and the test
 * proved nothing. Restarting the server really does sever the socket, which is what
 * EventSource's built-in retry (CONTRACTS.md section 4.10 emits `retry: 1000`) exists for.
 */
test.describe("SSE resilience", () => {
  test("survives a full page reload and rebuilds the stream", async ({ page }) => {
    await openTerminal(page);
    await page.reload();
    await expect(page.getByTestId("app-root")).toBeVisible();
    await expect(page.getByTestId("connection-status")).toHaveAttribute("data-status", "connected", {
      timeout: 30_000,
    });
    await expectPricesToTick(page);
  });

  test("recovers on its own after the stream is severed", async ({ page }) => {
    test.skip(
      !(await canRestartApp()),
      "needs the docker CLI or a mounted /var/run/docker.sock to bounce the app container",
    );
    test.slow();

    await openTerminal(page);
    const status = page.getByTestId("connection-status");
    await expect(status).toHaveAttribute("data-status", "connected");
    await expectPricesToTick(page);
    const beforeDrop = await readWatchlistPrices(page);

    await restartAppContainer();

    // The dot must notice the drop: "reconnecting" while EventSource retries,
    // "disconnected" if it has given up entirely.
    await expect
      .poll(async () => status.getAttribute("data-status"), {
        message: "the header dot never left 'connected' after the stream was severed",
        timeout: 60_000,
      })
      .not.toBe("connected");

    // ...and then recover with no reload and no user action.
    await expect(status).toHaveAttribute("data-status", "connected", { timeout: 90_000 });

    // Reconnected means ticking again, not merely a green dot.
    await expect
      .poll(
        async () => {
          const now = await readWatchlistPrices(page);
          return Object.entries(now).filter(
            ([t, v]) => beforeDrop[t] !== undefined && beforeDrop[t] !== v,
          ).length;
        },
        { message: "prices did not resume after the stream recovered", timeout: 60_000 },
      )
      .toBeGreaterThan(0);
  });
});
