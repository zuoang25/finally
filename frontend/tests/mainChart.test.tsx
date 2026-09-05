import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import MainChart from "@/components/MainChart";
import type { SparkPoint } from "@/hooks/usePriceStream";

// lightweight-charts draws to a canvas jsdom cannot implement; stub the wrapper
// so the assertions are about what MainChart decides to plot.
vi.mock("@/components/LineChart", () => ({
  default: ({ points, color }: { points: SparkPoint[]; color: string }) => (
    <div
      data-testid="line-chart"
      data-color={color}
      data-count={points.length}
      data-values={points.map((p) => p.value).join(",")}
    />
  ),
}));

const series: SparkPoint[] = [
  { time: 1757030400, value: 190 },
  { time: 1757030401, value: 192.5 },
  { time: 1757030402, value: 195 },
];

function renderChart(overrides: Partial<Parameters<typeof MainChart>[0]> = {}) {
  const props = {
    ticker: "AAPL" as string | null,
    points: series,
    price: 195 as number | null,
    dayChange: 5 as number | null,
    dayChangePercent: 2.6316 as number | null,
    ...overrides,
  };
  render(<MainChart {...props} />);
  return props;
}

describe("MainChart", () => {
  it("renders the panel and the selected symbol", () => {
    renderChart();
    expect(screen.getByTestId("main-chart")).toBeInTheDocument();
    expect(screen.getByTestId("main-chart-ticker")).toHaveTextContent("AAPL");
  });

  it("shows the live price and the day change", () => {
    renderChart();
    expect(screen.getByText("195.00")).toBeInTheDocument();
    expect(screen.getByText(/\+5\.00/)).toHaveTextContent("(+2.63%)");
  });

  it("renders a negative day change with a minus sign and red trace", () => {
    renderChart({ dayChange: -1.8, dayChangePercent: -1.2857 });
    expect(screen.getByText(/-1\.80/)).toHaveTextContent("(-1.29%)");
    expect(screen.getByTestId("line-chart")).toHaveAttribute("data-color", "#ff5c6c");
  });

  it("plots the accumulated session trace in green while up", () => {
    renderChart();
    const chart = screen.getByTestId("line-chart");
    expect(chart).toHaveAttribute("data-color", "#2fd07a");
    expect(chart).toHaveAttribute("data-count", "3");
    expect(chart).toHaveAttribute("data-values", "190,192.5,195");
    expect(screen.getByText("3 ticks this session")).toBeInTheDocument();
  });

  it("prompts for a selection when no ticker is chosen", () => {
    renderChart({ ticker: null, points: [], price: null, dayChange: null, dayChangePercent: null });
    expect(screen.getByTestId("main-chart")).toBeInTheDocument();
    expect(screen.getByTestId("main-chart-ticker")).toHaveTextContent("—");
    expect(screen.getByText(/Select a symbol in the watchlist/i)).toBeInTheDocument();
    expect(screen.queryByTestId("line-chart")).not.toBeInTheDocument();
    expect(screen.getByText("awaiting stream")).toBeInTheDocument();
  });

  it("waits for ticks when a symbol is selected but the stream is empty", () => {
    renderChart({ points: [], price: null, dayChange: null, dayChangePercent: null });
    expect(screen.getByText(/Waiting for AAPL price ticks/i)).toBeInTheDocument();
    expect(screen.queryByTestId("line-chart")).not.toBeInTheDocument();
  });

  it("needs two points before it draws a line", () => {
    const { rerender } = render(
      <MainChart ticker="AAPL" points={[series[0]]} price={190} dayChange={0} dayChangePercent={0} />,
    );
    expect(screen.queryByTestId("line-chart")).not.toBeInTheDocument();
    expect(screen.getByText("1 ticks this session")).toBeInTheDocument();

    rerender(
      <MainChart
        ticker="AAPL"
        points={series.slice(0, 2)}
        price={192.5}
        dayChange={2.5}
        dayChangePercent={1.3}
      />,
    );
    expect(screen.getByTestId("line-chart")).toHaveAttribute("data-count", "2");
  });

  it("renders em dashes rather than crashing when price and change are unknown", () => {
    renderChart({ price: null, dayChange: null, dayChangePercent: null });
    const ticker = screen.getByTestId("main-chart-ticker");
    expect(ticker).toHaveTextContent("AAPL");
    // price cell and the change cell both degrade to an em dash
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });
});
