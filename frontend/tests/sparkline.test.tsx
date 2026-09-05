import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Sparkline from "@/components/Sparkline";

describe("Sparkline", () => {
  it("renders a placeholder rule before two points have arrived", () => {
    const { container } = render(<Sparkline ticker="AAPL" points={[{ time: 1, value: 190 }]} />);
    expect(screen.getByTestId("watchlist-sparkline-AAPL")).toBeInTheDocument();
    expect(container.querySelector("line")).toBeInTheDocument();
    expect(container.querySelector("path")).toBeNull();
  });

  it("draws a trace once points accumulate", () => {
    const { container } = render(
      <Sparkline
        ticker="NVDA"
        points={[
          { time: 1, value: 138 },
          { time: 2, value: 139 },
          { time: 3, value: 140 },
        ]}
      />,
    );
    const paths = container.querySelectorAll("path");
    expect(paths).toHaveLength(2); // area fill + stroked line
    expect(paths[1].getAttribute("d")).toMatch(/^M0\.00,/);
  });

  it("colours the trace by its own direction", () => {
    const rising = render(
      <Sparkline ticker="UP" points={[{ time: 1, value: 1 }, { time: 2, value: 2 }]} />,
    );
    expect(rising.container.querySelectorAll("path")[1].getAttribute("stroke")).toBe(
      "var(--color-up)",
    );
    rising.unmount();

    const falling = render(
      <Sparkline ticker="DN" points={[{ time: 1, value: 2 }, { time: 2, value: 1 }]} />,
    );
    expect(falling.container.querySelectorAll("path")[1].getAttribute("stroke")).toBe(
      "var(--color-down)",
    );
  });

  it("survives a flat series without dividing by zero", () => {
    const { container } = render(
      <Sparkline ticker="FLAT" points={[{ time: 1, value: 5 }, { time: 2, value: 5 }]} />,
    );
    expect(container.querySelectorAll("path")[1].getAttribute("d")).not.toContain("NaN");
  });
});
