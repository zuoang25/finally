import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { MAX_SPARK_POINTS, accumulate, usePriceStream } from "@/hooks/usePriceStream";
import type { PriceMap } from "@/lib/types";

function tick(ticker: string, price: number, timestamp: number): PriceMap[string] {
  return {
    ticker,
    price,
    previous_price: price - 0.1,
    timestamp,
    change: 0.1,
    change_percent: 0.05,
    direction: "up",
  };
}

describe("accumulate", () => {
  it("appends one point per ticker from a ticker-keyed payload", () => {
    const first = accumulate({}, { AAPL: tick("AAPL", 190.5, 1), NVDA: tick("NVDA", 138.2, 1) });
    const second = accumulate(first, { AAPL: tick("AAPL", 191.0, 2) });

    expect(second.AAPL).toEqual([
      { time: 1, value: 190.5 },
      { time: 2, value: 191 },
    ]);
    expect(second.NVDA).toHaveLength(1);
  });

  it("caps the series and keeps the newest points", () => {
    let series = {};
    for (let i = 0; i < MAX_SPARK_POINTS + 25; i += 1) {
      series = accumulate(series, { AAPL: tick("AAPL", 100 + i, i) });
    }
    const points = (series as Record<string, { value: number }[]>).AAPL;
    expect(points).toHaveLength(MAX_SPARK_POINTS);
    expect(points[points.length - 1].value).toBe(100 + MAX_SPARK_POINTS + 24);
  });

  it("ignores entries without a finite price", () => {
    const series = accumulate({}, {
      AAPL: { ...tick("AAPL", 1, 1), price: Number.NaN },
    } as PriceMap);
    expect(series.AAPL).toBeUndefined();
  });
});

/** Controllable EventSource stand-in; jsdom does not implement one. */
class FakeEventSource {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  static last: FakeEventSource | null = null;

  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  onopen: ((e: Event) => void) | null = null;
  readyState = FakeEventSource.CONNECTING;
  closed = false;

  constructor(readonly url: string) {
    FakeEventSource.last = this;
  }

  open() {
    this.readyState = FakeEventSource.OPEN;
    this.onopen?.(new Event("open"));
  }

  emit(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent);
  }

  fail(readyState: number) {
    this.readyState = readyState;
    this.onerror?.(new Event("error"));
  }

  close() {
    this.closed = true;
    this.readyState = FakeEventSource.CLOSED;
  }
}

function Probe() {
  const { prices, series, connection } = usePriceStream("/api/stream/prices");
  return (
    <div>
      <span data-testid="conn">{connection}</span>
      <span data-testid="aapl">{prices.AAPL?.price ?? "none"}</span>
      <span data-testid="points">{series.AAPL?.length ?? 0}</span>
    </div>
  );
}

describe("usePriceStream", () => {
  beforeEach(() => {
    FakeEventSource.last = null;
    globalThis.EventSource = FakeEventSource as unknown as typeof EventSource;
  });

  it("starts disconnected and reports connected on the first message", async () => {
    render(<Probe />);
    expect(screen.getByTestId("conn")).toHaveTextContent("disconnected");

    const source = FakeEventSource.last!;
    expect(source.url).toBe("/api/stream/prices");

    await act(async () => {
      source.open();
      source.emit({ AAPL: tick("AAPL", 190.5, 1) });
    });

    expect(screen.getByTestId("conn")).toHaveTextContent("connected");
    expect(screen.getByTestId("aapl")).toHaveTextContent("190.5");
    expect(screen.getByTestId("points")).toHaveTextContent("1");
  });

  it("moves to reconnecting when a live stream drops, and disconnected when closed", async () => {
    render(<Probe />);
    const source = FakeEventSource.last!;

    await act(async () => {
      source.open();
      source.emit({ AAPL: tick("AAPL", 190.5, 1) });
    });
    await act(async () => {
      source.fail(FakeEventSource.CONNECTING);
    });
    expect(screen.getByTestId("conn")).toHaveTextContent("reconnecting");

    await act(async () => {
      source.fail(FakeEventSource.CLOSED);
    });
    await waitFor(() => expect(screen.getByTestId("conn")).toHaveTextContent("disconnected"));
  });

  it("ignores malformed payloads", async () => {
    render(<Probe />);
    const source = FakeEventSource.last!;
    await act(async () => {
      source.onmessage?.({ data: "not json" } as MessageEvent);
      source.onmessage?.({ data: "[1,2,3]" } as MessageEvent);
    });
    expect(screen.getByTestId("points")).toHaveTextContent("0");
  });

  it("closes the connection on unmount", () => {
    const { unmount } = render(<Probe />);
    const source = FakeEventSource.last!;
    unmount();
    expect(source.closed).toBe(true);
  });
});
