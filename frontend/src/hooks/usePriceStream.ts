"use client";

import { useEffect, useRef, useState } from "react";
import type { ConnectionState, PriceMap, PriceTick } from "@/lib/types";

/** Points kept per ticker for the sparklines and the main chart, since page load. */
export const MAX_SPARK_POINTS = 120;

/** One accumulated observation. `time` is the tick's epoch-seconds timestamp. */
export interface SparkPoint {
  time: number;
  value: number;
}

export type SeriesMap = Record<string, SparkPoint[]>;

export interface PriceStreamState {
  prices: PriceMap;
  /** Points per ticker, oldest first, capped at MAX_SPARK_POINTS. */
  series: SeriesMap;
  connection: ConnectionState;
}

/**
 * Merge one SSE payload (a ticker-keyed map, CONTRACTS §4.10) into the accumulated
 * per-ticker series. Exported so it can be tested without an EventSource.
 */
export function accumulate(series: SeriesMap, payload: PriceMap, cap = MAX_SPARK_POINTS): SeriesMap {
  const next: SeriesMap = { ...series };
  for (const [ticker, tick] of Object.entries(payload)) {
    if (typeof tick?.price !== "number" || !Number.isFinite(tick.price)) continue;
    const time = Number.isFinite(tick.timestamp) ? tick.timestamp : Date.now() / 1000;
    const points = next[ticker] ?? [];
    const appended = [...points, { time, value: tick.price }];
    next[ticker] = appended.length > cap ? appended.slice(appended.length - cap) : appended;
  }
  return next;
}

function parsePayload(raw: string): PriceMap | null {
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return null;
    return parsed as Record<string, PriceTick>;
  } catch {
    return null;
  }
}

/**
 * Live prices over SSE. EventSource retries on its own, so a dropped connection
 * moves the header dot to "reconnecting" rather than tearing anything down.
 */
export function usePriceStream(url = "/api/stream/prices"): PriceStreamState {
  const [prices, setPrices] = useState<PriceMap>({});
  const [series, setSeries] = useState<SeriesMap>({});
  const [connection, setConnection] = useState<ConnectionState>("disconnected");
  const everConnected = useRef(false);

  useEffect(() => {
    if (typeof window === "undefined" || typeof EventSource === "undefined") return;

    const source = new EventSource(url);

    source.onopen = () => {
      everConnected.current = true;
      setConnection("connected");
    };

    source.onmessage = (event: MessageEvent) => {
      const payload = parsePayload(String(event.data));
      if (!payload) return;
      everConnected.current = true;
      setConnection("connected");
      setPrices((prev) => ({ ...prev, ...payload }));
      setSeries((prev) => accumulate(prev, payload));
    };

    source.onerror = () => {
      // EventSource retries automatically unless it has been closed for good.
      setConnection(
        source.readyState === EventSource.CLOSED
          ? "disconnected"
          : everConnected.current
            ? "reconnecting"
            : "disconnected",
      );
    };

    return () => source.close();
  }, [url]);

  return { prices, series, connection };
}
