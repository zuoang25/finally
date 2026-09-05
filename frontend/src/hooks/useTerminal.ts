"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "@/lib/api";
import type { Portfolio, Snapshot, WatchlistItem } from "@/lib/types";

export interface TerminalData {
  portfolio: Portfolio | null;
  watchlist: WatchlistItem[];
  snapshots: Snapshot[];
  loading: boolean;
  error: string | null;
  /** Refetch portfolio + watchlist + history so every panel converges after a mutation. */
  refresh: () => Promise<void>;
}

/** Snapshot polling cadence; the backend appends a row every 30 s. */
const HISTORY_POLL_MS = 30_000;

export function useTerminal(): TerminalData {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [nextPortfolio, nextWatchlist, history] = await Promise.all([
        api.getPortfolio(),
        api.getWatchlist(),
        api.getHistory(),
      ]);
      setPortfolio(nextPortfolio);
      setWatchlist(nextWatchlist.tickers ?? []);
      setSnapshots(history.snapshots ?? []);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load terminal data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), HISTORY_POLL_MS);
    return () => clearInterval(timer);
  }, [refresh]);

  return { portfolio, watchlist, snapshots, loading, error, refresh };
}
