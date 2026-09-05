import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import WatchlistPanel from "@/components/WatchlistPanel";
import { ApiError } from "@/lib/api";
import { prices, watchlist } from "./fixtures";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: { addTicker: vi.fn(), removeTicker: vi.fn() },
  };
});

const { api } = await import("@/lib/api");
const addTicker = api.addTicker as unknown as ReturnType<typeof vi.fn>;
const removeTicker = api.removeTicker as unknown as ReturnType<typeof vi.fn>;

function renderPanel(overrides: Partial<Parameters<typeof WatchlistPanel>[0]> = {}) {
  const props = {
    items: watchlist,
    prices,
    series: { AAPL: [{ time: 1, value: 190 }, { time: 2, value: 191 }] },
    selected: "AAPL",
    onSelect: vi.fn(),
    onChanged: vi.fn(),
    loading: false,
    ...overrides,
  };
  render(<WatchlistPanel {...props} />);
  return props;
}

describe("WatchlistPanel", () => {
  beforeEach(() => {
    addTicker.mockReset().mockResolvedValue(undefined);
    removeTicker.mockReset().mockResolvedValue(undefined);
  });

  it("renders one row per ticker with the contract testids", () => {
    renderPanel();
    expect(screen.getByTestId("watchlist")).toBeInTheDocument();
    for (const t of ["AAPL", "NVDA", "PYPL"]) {
      expect(screen.getByTestId(`watchlist-row-${t}`)).toBeInTheDocument();
      expect(screen.getByTestId(`watchlist-price-${t}`)).toBeInTheDocument();
      expect(screen.getByTestId(`watchlist-change-${t}`)).toBeInTheDocument();
      expect(screen.getByTestId(`watchlist-sparkline-${t}`)).toBeInTheDocument();
      expect(screen.getByTestId(`watchlist-remove-${t}`)).toBeInTheDocument();
    }
  });

  it("prefers the streamed price over the REST snapshot", () => {
    renderPanel();
    // Fixture REST price is 190.50; the stream says 195.00.
    expect(screen.getByTestId("watchlist-price-AAPL")).toHaveTextContent("195.00");
  });

  it("recomputes the day change against the session open as prices stream in", () => {
    renderPanel();
    // AAPL opened at 190.00 and streams at 195.00 -> +2.63%
    expect(screen.getByTestId("watchlist-change-AAPL")).toHaveTextContent("+2.63%");
    expect(screen.getByTestId("watchlist-change-NVDA")).toHaveTextContent("-1.29%");
  });

  it("shows an em dash for a ticker that has no price yet", () => {
    renderPanel();
    expect(screen.getByTestId("watchlist-price-PYPL")).toHaveTextContent("—");
    expect(screen.getByTestId("watchlist-change-PYPL")).toHaveTextContent("—");
  });

  it("selects a ticker when its row is clicked", async () => {
    const props = renderPanel();
    await userEvent.click(screen.getByTestId("watchlist-row-NVDA"));
    expect(props.onSelect).toHaveBeenCalledWith("NVDA");
  });

  it("adds a ticker, upper-casing the input, and refreshes", async () => {
    const props = renderPanel();
    await userEvent.type(screen.getByTestId("watchlist-add-input"), "pypl");
    await userEvent.click(screen.getByTestId("watchlist-add-button"));

    await waitFor(() => expect(addTicker).toHaveBeenCalledWith("PYPL"));
    expect(props.onChanged).toHaveBeenCalled();
    expect(screen.queryByTestId("watchlist-error")).not.toBeInTheDocument();
  });

  it("rejects a malformed symbol before calling the API", async () => {
    renderPanel();
    await userEvent.type(screen.getByTestId("watchlist-add-input"), "1234");
    await userEvent.click(screen.getByTestId("watchlist-add-button"));

    expect(await screen.findByTestId("watchlist-error")).toHaveTextContent("not a valid symbol");
    expect(addTicker).not.toHaveBeenCalled();
  });

  it("surfaces a backend rejection inline", async () => {
    addTicker.mockRejectedValue(new ApiError(409, "AAPL is already on the watchlist"));
    renderPanel();
    await userEvent.type(screen.getByTestId("watchlist-add-input"), "AAPL");
    await userEvent.click(screen.getByTestId("watchlist-add-button"));

    expect(await screen.findByTestId("watchlist-error")).toHaveTextContent(
      "AAPL is already on the watchlist",
    );
  });

  it("removes a ticker without selecting the row", async () => {
    const props = renderPanel();
    await userEvent.click(screen.getByTestId("watchlist-remove-NVDA"));

    await waitFor(() => expect(removeTicker).toHaveBeenCalledWith("NVDA"));
    expect(props.onSelect).not.toHaveBeenCalled();
    expect(props.onChanged).toHaveBeenCalled();
  });

  it("renders an empty state when nothing is watched", () => {
    renderPanel({ items: [] });
    expect(screen.getByText(/No symbols yet/i)).toBeInTheDocument();
  });

  it("does not render an error element when there is no error", () => {
    renderPanel();
    expect(screen.queryByTestId("watchlist-error")).not.toBeInTheDocument();
  });
});
