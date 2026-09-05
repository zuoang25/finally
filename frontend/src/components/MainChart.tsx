"use client";

import LineChart from "./LineChart";
import Panel from "./Panel";
import { flashClass, usePriceFlash } from "@/hooks/usePriceFlash";
import type { SparkPoint } from "@/hooks/usePriceStream";
import { formatPercent, formatPrice, signClass } from "@/lib/format";

interface MainChartProps {
  ticker: string | null;
  points: SparkPoint[];
  price: number | null;
  dayChange: number | null;
  dayChangePercent: number | null;
}

/**
 * The one loud element on the terminal: the selected symbol, its live price and
 * the trace accumulated since page load.
 */
export default function MainChart({
  ticker,
  points,
  price,
  dayChange,
  dayChangePercent,
}: MainChartProps) {
  const flash = usePriceFlash(price);
  const rising = (dayChangePercent ?? 0) >= 0;
  const color = rising ? "#2fd07a" : "#ff5c6c";

  return (
    <Panel
      title="Chart"
      testId="main-chart"
      className="min-h-0 border-b border-line"
      bodyClassName="relative"
      right={
        <span className="text-[11px] text-dim">
          {points.length > 0 ? `${points.length} ticks this session` : "awaiting stream"}
        </span>
      }
    >
      <div className="pointer-events-none absolute left-4 top-3 z-10 flex items-end gap-4">
        <div>
          <div
            data-testid="main-chart-ticker"
            className="num text-[22px] font-semibold leading-none tracking-wide text-ink"
          >
            {ticker ?? "—"}
          </div>
          <div className="mt-1 text-[11px] text-dim">Session trace</div>
        </div>
        <div className="flex items-end gap-3">
          <span className={`num rounded px-1 text-[26px] font-semibold leading-none ${flashClass(flash)}`}>
            {formatPrice(price)}
          </span>
          <span className={`num pb-0.5 text-[13px] ${signClass(dayChangePercent)}`}>
            {dayChange === null
              ? "—"
              : `${dayChange >= 0 ? "+" : "-"}${formatPrice(Math.abs(dayChange))}`}{" "}
            ({formatPercent(dayChangePercent)})
          </span>
        </div>
      </div>

      <div className="grid-lines absolute inset-0">
        {points.length >= 2 ? (
          <LineChart points={points} color={color} precision={2} />
        ) : (
          <div className="flex h-full items-center justify-center text-[12px] text-dim">
            {ticker
              ? `Waiting for ${ticker} price ticks…`
              : "Select a symbol in the watchlist to chart it."}
          </div>
        )}
      </div>
    </Panel>
  );
}
