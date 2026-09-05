import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import WatchlistRow from "@/components/WatchlistRow";
import { FLASH_MS } from "@/hooks/usePriceFlash";
import { watchlist } from "./fixtures";

const item = watchlist[0];

function Row({ price }: { price: number }) {
  return (
    <WatchlistRow
      item={item}
      livePrice={price}
      points={[]}
      selected={false}
      onSelect={vi.fn()}
      onRemove={vi.fn()}
      removing={false}
    />
  );
}

describe("price flash", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("does not flash on first render", () => {
    render(<Row price={190} />);
    const cell = screen.getByTestId("watchlist-price-AAPL");
    expect(cell.className).not.toMatch(/flash-/);
  });

  it("applies the up class on an uptick and clears it after the timeout", () => {
    const { rerender } = render(<Row price={190} />);
    const cell = () => screen.getByTestId("watchlist-price-AAPL");

    act(() => {
      rerender(<Row price={191} />);
    });
    expect(cell().className).toContain("flash-up");

    act(() => {
      vi.advanceTimersByTime(FLASH_MS + 10);
    });
    expect(cell().className).not.toMatch(/flash-/);
  });

  it("applies the down class on a downtick", () => {
    const { rerender } = render(<Row price={191} />);
    act(() => {
      rerender(<Row price={189.5} />);
    });
    expect(screen.getByTestId("watchlist-price-AAPL").className).toContain("flash-down");
  });

  it("does not flash when the price is unchanged", () => {
    const { rerender } = render(<Row price={190} />);
    act(() => {
      rerender(<Row price={190} />);
    });
    expect(screen.getByTestId("watchlist-price-AAPL").className).not.toMatch(/flash-/);
  });
});
