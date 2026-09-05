"use client";

import Sparkline from "./Sparkline";
import { flashClass, usePriceFlash } from "@/hooks/usePriceFlash";
import type { SparkPoint } from "@/hooks/usePriceStream";
import { formatPercent, formatPrice, signClass } from "@/lib/format";
import type { WatchlistItem } from "@/lib/types";

interface WatchlistRowProps {
  item: WatchlistItem;
  /** Latest streamed price; falls back to the REST snapshot when the stream is quiet. */
  livePrice: number | null;
  points: SparkPoint[];
  selected: boolean;
  onSelect: (ticker: string) => void;
  onRemove: (ticker: string) => void;
  removing: boolean;
}

export default function WatchlistRow({
  item,
  livePrice,
  points,
  selected,
  onSelect,
  onRemove,
  removing,
}: WatchlistRowProps) {
  const price = livePrice ?? item.price;
  const flash = usePriceFlash(price);

  // Day change tracks the session open, so recompute it as live prices arrive
  // instead of waiting for the next /api/watchlist refetch.
  const dayChangePercent =
    price !== null && item.open_price ? ((price - item.open_price) / item.open_price) * 100 : item.change_percent;

  return (
    <div
      data-testid={`watchlist-row-${item.ticker}`}
      role="row"
      tabIndex={0}
      aria-selected={selected}
      onClick={() => onSelect(item.ticker)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(item.ticker);
        }
      }}
      className={`group grid cursor-pointer grid-cols-[minmax(0,1fr)_68px_60px_64px_18px] items-center gap-2 border-l-2 px-3 py-1.5 transition-colors ${
        selected
          ? "border-l-accent bg-raised"
          : "border-l-transparent hover:bg-surface-2"
      }`}
    >
      <span className="num truncate text-[13px] font-semibold tracking-wide text-ink">
        {item.ticker}
      </span>

      <span
        data-testid={`watchlist-price-${item.ticker}`}
        className={`num rounded px-1 text-right text-[13px] tabular-nums ${flashClass(flash)}`}
      >
        {formatPrice(price)}
      </span>

      <span
        data-testid={`watchlist-change-${item.ticker}`}
        className={`num text-right text-[12px] ${signClass(dayChangePercent)}`}
      >
        {formatPercent(dayChangePercent)}
      </span>

      <span className="flex justify-end">
        <Sparkline ticker={item.ticker} points={points} />
      </span>

      <button
        type="button"
        data-testid={`watchlist-remove-${item.ticker}`}
        aria-label={`Remove ${item.ticker} from watchlist`}
        disabled={removing}
        onClick={(e) => {
          e.stopPropagation();
          onRemove(item.ticker);
        }}
        className="text-dim opacity-0 transition hover:text-down focus-visible:opacity-100 group-hover:opacity-100 disabled:cursor-not-allowed"
      >
        <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
          <path
            d="M2.5 2.5l7 7M9.5 2.5l-7 7"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
          />
        </svg>
      </button>
    </div>
  );
}
