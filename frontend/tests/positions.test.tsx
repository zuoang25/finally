import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import PositionsTable from "@/components/PositionsTable";
import { portfolio, prices } from "./fixtures";

function renderTable(overrides: Partial<Parameters<typeof PositionsTable>[0]> = {}) {
  const props = {
    positions: portfolio.positions,
    prices,
    selected: null as string | null,
    onSelect: vi.fn(),
    loading: false,
    ...overrides,
  };
  render(<PositionsTable {...props} />);
  return props;
}

describe("PositionsTable", () => {
  it("renders every contract cell for each position", () => {
    renderTable();
    expect(screen.getByTestId("positions-table")).toBeInTheDocument();
    for (const t of ["AAPL", "NVDA"]) {
      expect(screen.getByTestId(`position-row-${t}`)).toBeInTheDocument();
      expect(screen.getByTestId(`position-quantity-${t}`)).toBeInTheDocument();
      expect(screen.getByTestId(`position-avgcost-${t}`)).toBeInTheDocument();
      expect(screen.getByTestId(`position-price-${t}`)).toBeInTheDocument();
      expect(screen.getByTestId(`position-pnl-${t}`)).toBeInTheDocument();
      expect(screen.getByTestId(`position-pnlpct-${t}`)).toBeInTheDocument();
    }
  });

  it("revalues P&L against the streamed price", () => {
    renderTable();
    // AAPL: 10 @ avg 190, streaming at 195 -> +$50.00 / +2.63%
    expect(screen.getByTestId("position-pnl-AAPL")).toHaveTextContent("+$50.00");
    expect(screen.getByTestId("position-pnlpct-AAPL")).toHaveTextContent("+2.63%");
  });

  it("colours gains green and losses red", () => {
    renderTable();
    expect(screen.getByTestId("position-pnl-AAPL").className).toContain("text-up");
    expect(screen.getByTestId("position-pnl-NVDA").className).toContain("text-down");
  });

  it("falls back to the REST price when the stream has no quote", () => {
    renderTable({ prices: {} });
    expect(screen.getByTestId("position-price-AAPL")).toHaveTextContent("195.00");
  });

  it("formats quantity and average cost", () => {
    renderTable();
    expect(screen.getByTestId("position-quantity-AAPL")).toHaveTextContent("10");
    expect(screen.getByTestId("position-avgcost-AAPL")).toHaveTextContent("190.00");
  });

  it("shows the empty state only when there are no positions", () => {
    const { rerender } = render(
      <PositionsTable positions={[]} prices={{}} selected={null} onSelect={vi.fn()} loading={false} />,
    );
    expect(screen.getByTestId("positions-empty")).toBeInTheDocument();

    rerender(
      <PositionsTable
        positions={portfolio.positions}
        prices={prices}
        selected={null}
        onSelect={vi.fn()}
        loading={false}
      />,
    );
    expect(screen.queryByTestId("positions-empty")).not.toBeInTheDocument();
  });

  it("selects a ticker when a row is clicked", async () => {
    const props = renderTable();
    await userEvent.click(screen.getByTestId("position-row-NVDA"));
    expect(props.onSelect).toHaveBeenCalledWith("NVDA");
  });
});
