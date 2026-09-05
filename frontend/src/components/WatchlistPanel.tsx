"use client";

import { useState } from "react";
import Panel from "./Panel";
import WatchlistRow from "./WatchlistRow";
import { ApiError, api } from "@/lib/api";
import { isValidTicker, normalizeTicker } from "@/lib/format";
import type { SeriesMap } from "@/hooks/usePriceStream";
import type { PriceMap, WatchlistItem } from "@/lib/types";

interface WatchlistPanelProps {
  items: WatchlistItem[];
  prices: PriceMap;
  series: SeriesMap;
  selected: string | null;
  onSelect: (ticker: string) => void;
  onChanged: () => Promise<void> | void;
  loading: boolean;
}

export default function WatchlistPanel({
  items,
  prices,
  series,
  selected,
  onSelect,
  onChanged,
  loading,
}: WatchlistPanelProps) {
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    const ticker = normalizeTicker(draft);
    if (!ticker) return;
    if (!isValidTicker(ticker)) {
      setError(`${ticker} is not a valid symbol.`);
      return;
    }

    setBusy(true);
    setError(null);
    try {
      await api.addTicker(ticker);
      setDraft("");
      await onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : `Could not add ${ticker}.`);
    } finally {
      setBusy(false);
    }
  }

  async function handleRemove(ticker: string) {
    setRemoving(ticker);
    setError(null);
    try {
      await api.removeTicker(ticker);
      await onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : `Could not remove ${ticker}.`);
    } finally {
      setRemoving(null);
    }
  }

  return (
    <Panel
      title="Watchlist"
      tick="var(--color-accent)"
      testId="watchlist"
      className="h-full border-r border-line"
      bodyClassName="flex flex-col"
      right={<span className="num text-[11px] text-dim">{items.length}</span>}
    >
      <div className="grid grid-cols-[minmax(0,1fr)_68px_60px_64px_18px] gap-2 border-b border-line-soft px-3 py-1 text-[10px] text-dim">
        <span>Symbol</span>
        <span className="text-right">Last</span>
        <span className="text-right">Day</span>
        <span className="text-right">Trace</span>
        <span />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto" role="rowgroup">
        {loading && items.length === 0 ? (
          <p className="px-3 py-4 text-[12px] text-dim">Loading symbols…</p>
        ) : items.length === 0 ? (
          <p className="px-3 py-4 text-[12px] text-dim">
            No symbols yet. Add one below to start streaming prices.
          </p>
        ) : (
          items.map((item) => (
            <WatchlistRow
              key={item.ticker}
              item={item}
              livePrice={prices[item.ticker]?.price ?? null}
              points={series[item.ticker] ?? []}
              selected={selected === item.ticker}
              onSelect={onSelect}
              onRemove={handleRemove}
              removing={removing === item.ticker}
            />
          ))
        )}
      </div>

      <form onSubmit={handleAdd} className="shrink-0 border-t border-line p-2">
        <div className="flex gap-1.5">
          <input
            data-testid="watchlist-add-input"
            aria-label="Add a ticker to the watchlist"
            placeholder="Add symbol"
            value={draft}
            maxLength={10}
            onChange={(e) => setDraft(e.target.value.toUpperCase())}
            className="num min-w-0 flex-1 rounded-sm border border-line bg-ground px-2 py-1.5 text-[12px] uppercase text-ink placeholder:font-sans placeholder:normal-case placeholder:text-dim focus:border-blue focus:outline-none"
          />
          <button
            type="submit"
            data-testid="watchlist-add-button"
            disabled={busy}
            className="rounded-sm bg-purple px-3 py-1.5 text-[12px] font-semibold text-white transition hover:brightness-115 disabled:opacity-50"
          >
            {busy ? "Adding…" : "Add"}
          </button>
        </div>
        {error ? (
          <p data-testid="watchlist-error" role="alert" className="mt-1.5 text-[11px] text-down">
            {error}
          </p>
        ) : null}
      </form>
    </Panel>
  );
}
