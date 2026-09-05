import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import TradeBar from "@/components/TradeBar";
import { ApiError } from "@/lib/api";
import { prices } from "./fixtures";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { trade: vi.fn() } };
});

const { api } = await import("@/lib/api");
const trade = api.trade as unknown as ReturnType<typeof vi.fn>;

const filled = {
  trade: {
    id: "t1",
    ticker: "AAPL",
    side: "buy" as const,
    quantity: 3,
    price: 195,
    executed_at: "2026-09-05T10:01:00Z",
  },
  portfolio: null,
};

describe("TradeBar", () => {
  beforeEach(() => {
    trade.mockReset().mockResolvedValue(filled);
  });

  it("pre-fills the ticker from the selected symbol", () => {
    render(<TradeBar ticker="NVDA" prices={prices} onTraded={vi.fn()} />);
    expect(screen.getByTestId("trade-ticker-input")).toHaveValue("NVDA");
  });

  it("submits a buy and shows a confirmation", async () => {
    const onTraded = vi.fn();
    render(<TradeBar ticker="AAPL" prices={prices} onTraded={onTraded} />);

    await userEvent.type(screen.getByTestId("trade-quantity-input"), "3");
    await userEvent.click(screen.getByTestId("trade-buy-button"));

    await waitFor(() => expect(trade).toHaveBeenCalledWith("AAPL", 3, "buy"));
    expect(await screen.findByTestId("trade-success")).toHaveTextContent("Bought 3 AAPL at 195.00");
    expect(onTraded).toHaveBeenCalled();
    expect(screen.queryByTestId("trade-error")).not.toBeInTheDocument();
  });

  it("submits a sell", async () => {
    trade.mockResolvedValue({ ...filled, trade: { ...filled.trade, side: "sell" as const } });
    render(<TradeBar ticker="AAPL" prices={prices} onTraded={vi.fn()} />);

    await userEvent.type(screen.getByTestId("trade-quantity-input"), "3");
    await userEvent.click(screen.getByTestId("trade-sell-button"));

    await waitFor(() => expect(trade).toHaveBeenCalledWith("AAPL", 3, "sell"));
    expect(await screen.findByTestId("trade-success")).toHaveTextContent("Sold 3 AAPL");
  });

  it("blocks a missing or zero quantity before hitting the API", async () => {
    render(<TradeBar ticker="AAPL" prices={prices} onTraded={vi.fn()} />);
    await userEvent.click(screen.getByTestId("trade-buy-button"));

    expect(await screen.findByTestId("trade-error")).toHaveTextContent("quantity greater than zero");
    expect(trade).not.toHaveBeenCalled();
  });

  it("blocks an empty ticker", async () => {
    render(<TradeBar ticker={null} prices={prices} onTraded={vi.fn()} />);
    await userEvent.type(screen.getByTestId("trade-quantity-input"), "2");
    await userEvent.click(screen.getByTestId("trade-buy-button"));

    expect(await screen.findByTestId("trade-error")).toHaveTextContent("Enter a symbol");
    expect(trade).not.toHaveBeenCalled();
  });

  it("surfaces the backend's insufficient-cash message", async () => {
    trade.mockRejectedValue(
      new ApiError(400, "Insufficient cash: need $250000.00, have $8050.00"),
    );
    render(<TradeBar ticker="TSLA" prices={prices} onTraded={vi.fn()} />);

    await userEvent.type(screen.getByTestId("trade-quantity-input"), "1000");
    await userEvent.click(screen.getByTestId("trade-buy-button"));

    expect(await screen.findByTestId("trade-error")).toHaveTextContent("Insufficient cash");
    expect(screen.queryByTestId("trade-success")).not.toBeInTheDocument();
  });

  it("shows the live quote and an order estimate", async () => {
    render(<TradeBar ticker="AAPL" prices={prices} onTraded={vi.fn()} />);
    expect(screen.getByText(/Last 195\.00/)).toBeInTheDocument();

    await userEvent.type(screen.getByTestId("trade-quantity-input"), "2");
    expect(screen.getByText(/est\. 390\.00/)).toBeInTheDocument();
  });

  it("renders neither banner at rest", () => {
    render(<TradeBar ticker="AAPL" prices={prices} onTraded={vi.fn()} />);
    expect(screen.queryByTestId("trade-error")).not.toBeInTheDocument();
    expect(screen.queryByTestId("trade-success")).not.toBeInTheDocument();
  });
});
