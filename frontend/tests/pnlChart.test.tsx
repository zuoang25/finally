import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import PnlChart from "@/components/PnlChart";
import type { ChartPoint } from "@/components/LineChart";
import { snapshots } from "./fixtures";

// lightweight-charts draws to a canvas jsdom cannot implement; stub the wrapper
// so the assertions are about the series PnlChart derives from the snapshots.
vi.mock("@/components/LineChart", () => ({
  default: ({ points, color }: { points: ChartPoint[]; color: string }) => (
    <div
      data-testid="line-chart"
      data-color={color}
      data-count={points.length}
      data-values={points.map((p) => p.value).join(",")}
    />
  ),
}));

describe("PnlChart", () => {
  it("renders the panel container", () => {
    render(<PnlChart snapshots={snapshots} liveTotal={null} />);
    expect(screen.getByTestId("pnl-chart")).toBeInTheDocument();
  });

  it("plots one point per snapshot, oldest first", () => {
    render(<PnlChart snapshots={snapshots} liveTotal={null} />);
    const chart = screen.getByTestId("line-chart");
    expect(chart).toHaveAttribute("data-count", "3");
    expect(chart).toHaveAttribute("data-values", "10000,10120.5,10552.8");
  });

  it("appends the live total as the trailing point", () => {
    render(<PnlChart snapshots={snapshots} liveTotal={10600} />);
    const chart = screen.getByTestId("line-chart");
    expect(chart).toHaveAttribute("data-count", "4");
    expect(chart).toHaveAttribute("data-values", "10000,10120.5,10552.8,10600");
  });

  it("reports the session delta against the first snapshot", () => {
    render(<PnlChart snapshots={snapshots} liveTotal={null} />);
    // 10000 -> 10552.80 is +$552.80 / +5.53%
    expect(screen.getByText(/\+\$552\.80/)).toHaveTextContent("(+5.53%)");
    expect(screen.getByTestId("line-chart")).toHaveAttribute("data-color", "#209dd7");
  });

  it("turns red when the book is below where it started", () => {
    render(
      <PnlChart
        snapshots={[
          { total_value: 10000, recorded_at: "2026-09-05T10:00:00Z" },
          { total_value: 9500, recorded_at: "2026-09-05T10:00:30Z" },
        ]}
        liveTotal={null}
      />,
    );
    expect(screen.getByText(/-\$500\.00/)).toHaveTextContent("(-5.00%)");
    expect(screen.getByTestId("line-chart")).toHaveAttribute("data-color", "#ff5c6c");
  });

  it("explains itself instead of drawing with no snapshots", () => {
    render(<PnlChart snapshots={[]} liveTotal={null} />);
    expect(screen.getByTestId("pnl-chart")).toBeInTheDocument();
    expect(screen.queryByTestId("line-chart")).not.toBeInTheDocument();
    expect(screen.getByText(/recorded every 30 seconds/i)).toBeInTheDocument();
  });

  it("still holds off with a single snapshot and no live total", () => {
    render(<PnlChart snapshots={[snapshots[0]]} liveTotal={null} />);
    expect(screen.queryByTestId("line-chart")).not.toBeInTheDocument();
  });

  it("draws as soon as a live total joins a single snapshot", () => {
    render(<PnlChart snapshots={[snapshots[0]]} liveTotal={10250} />);
    const chart = screen.getByTestId("line-chart");
    expect(chart).toHaveAttribute("data-count", "2");
    expect(chart).toHaveAttribute("data-values", "10000,10250");
  });

  it("draws nothing from a live total alone", () => {
    render(<PnlChart snapshots={[]} liveTotal={10000} />);
    expect(screen.queryByTestId("line-chart")).not.toBeInTheDocument();
    expect(screen.getByTestId("pnl-chart")).toBeInTheDocument();
  });

  it("drops snapshots with an unparseable timestamp", () => {
    render(
      <PnlChart
        snapshots={[
          { total_value: 10000, recorded_at: "2026-09-05T10:00:00Z" },
          { total_value: 1, recorded_at: "not-a-date" },
          { total_value: 10500, recorded_at: "2026-09-05T10:01:00Z" },
        ]}
        liveTotal={null}
      />,
    );
    expect(screen.getByTestId("line-chart")).toHaveAttribute("data-values", "10000,10500");
  });

  it("ignores a non-finite live total", () => {
    render(<PnlChart snapshots={snapshots} liveTotal={Number.NaN} />);
    expect(screen.getByTestId("line-chart")).toHaveAttribute("data-count", "3");
  });
});
