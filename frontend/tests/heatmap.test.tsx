import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import HeatmapPanel from "@/components/HeatmapPanel";
import { portfolio } from "./fixtures";

describe("HeatmapPanel", () => {
  it("renders one tile per position", () => {
    render(<HeatmapPanel positions={portfolio.positions} onSelect={vi.fn()} />);
    expect(screen.getByTestId("portfolio-heatmap")).toBeInTheDocument();
    expect(screen.getByTestId("heatmap-tile-AAPL")).toBeInTheDocument();
    expect(screen.getByTestId("heatmap-tile-NVDA")).toBeInTheDocument();
  });

  it("sizes tiles by market value", () => {
    render(<HeatmapPanel positions={portfolio.positions} onSelect={vi.fn()} />);
    const area = (t: string) => {
      const el = screen.getByTestId(`heatmap-tile-${t}`);
      return Number.parseFloat(el.style.width) * Number.parseFloat(el.style.height);
    };
    expect(area("AAPL")).toBeGreaterThan(area("NVDA"));
  });

  it("colours a winning tile green and a losing tile red", () => {
    render(<HeatmapPanel positions={portfolio.positions} onSelect={vi.fn()} />);
    expect(screen.getByTestId("heatmap-tile-AAPL").style.background).toContain("47, 208, 122");
    expect(screen.getByTestId("heatmap-tile-NVDA").style.background).toContain("255, 92, 108");
  });

  it("selects the ticker when a tile is clicked", async () => {
    const onSelect = vi.fn();
    render(<HeatmapPanel positions={portfolio.positions} onSelect={onSelect} />);
    await userEvent.click(screen.getByTestId("heatmap-tile-NVDA"));
    expect(onSelect).toHaveBeenCalledWith("NVDA");
  });

  it("renders an empty state with no positions", () => {
    render(<HeatmapPanel positions={[]} onSelect={vi.fn()} />);
    expect(screen.getByTestId("portfolio-heatmap")).toBeInTheDocument();
    expect(screen.getByText(/Buy a position/i)).toBeInTheDocument();
  });
});
