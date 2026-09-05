"use client";

import { useEffect, useRef, useState } from "react";
import Panel from "./Panel";
import { formatPercent, formatSignedMoney } from "@/lib/format";
import { squarify } from "@/lib/treemap";
import type { Position } from "@/lib/types";

interface HeatmapPanelProps {
  positions: Position[];
  onSelect: (ticker: string) => void;
}

/** Map P&L% to a colour ramp: deep red through neutral slate to deep green. */
function tileColor(pnlPercent: number): string {
  const magnitude = Math.min(Math.abs(pnlPercent) / 8, 1);
  const alpha = 0.16 + magnitude * 0.62;
  if (Math.abs(pnlPercent) < 0.005) return "rgba(93,106,125,0.28)";
  return pnlPercent > 0 ? `rgba(47,208,122,${alpha})` : `rgba(255,92,108,${alpha})`;
}

export default function HeatmapPanel({ positions, onSelect }: HeatmapPanelProps) {
  const boxRef = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const measure = () => setSize({ width: el.clientWidth, height: el.clientHeight });
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Fall back to a nominal box so tiles still render in environments without layout.
  const width = size.width || 320;
  const height = size.height || 180;
  const tiles = squarify(
    positions.map((p) => ({ key: p.ticker, value: p.market_value, position: p })),
    width,
    height,
  );

  return (
    <Panel
      title="Allocation"
      tick="var(--color-blue)"
      testId="portfolio-heatmap"
      className="min-h-0"
      bodyClassName="relative"
      right={<span className="text-[11px] text-dim">sized by weight · coloured by P&amp;L</span>}
    >
      <div ref={boxRef} className="absolute inset-0 overflow-hidden">
        {positions.length === 0 ? (
          <div className="flex h-full items-center justify-center px-4 text-center text-[12px] text-dim">
            Buy a position and it appears here, sized by its share of the portfolio.
          </div>
        ) : (
          tiles.map(({ item, x, y, width: w, height: h }) => {
            const p = item.position;
            const compact = w < 62 || h < 34;
            return (
              <button
                key={p.ticker}
                type="button"
                data-testid={`heatmap-tile-${p.ticker}`}
                onClick={() => onSelect(p.ticker)}
                title={`${p.ticker} · ${p.weight.toFixed(1)}% of portfolio · ${formatSignedMoney(p.unrealized_pnl)}`}
                style={{
                  position: "absolute",
                  left: x,
                  top: y,
                  width: w,
                  height: h,
                  background: tileColor(p.unrealized_pnl_percent),
                }}
                className="overflow-hidden border border-ground/70 px-1.5 py-1 text-left transition hover:brightness-125"
              >
                <span className="num block truncate text-[12px] font-semibold text-ink">
                  {p.ticker}
                </span>
                {!compact && (
                  <>
                    <span className="num block truncate text-[11px] text-ink/80">
                      {formatPercent(p.unrealized_pnl_percent)}
                    </span>
                    <span className="num block truncate text-[10px] text-ink/55">
                      {p.weight.toFixed(1)}%
                    </span>
                  </>
                )}
              </button>
            );
          })
        )}
      </div>
    </Panel>
  );
}
