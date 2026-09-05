"use client";

import Panel from "./Panel";
import { flashClass, usePriceFlash } from "@/hooks/usePriceFlash";
import {
  formatMoney,
  formatPercent,
  formatPrice,
  formatQuantity,
  formatSignedMoney,
  signClass,
} from "@/lib/format";
import type { PriceMap, Position } from "@/lib/types";

interface PositionsTableProps {
  positions: Position[];
  prices: PriceMap;
  selected: string | null;
  onSelect: (ticker: string) => void;
  loading: boolean;
}

const COLUMNS = "grid-cols-[minmax(64px,1fr)_80px_88px_88px_100px_84px]";

function PositionRow({
  position,
  livePrice,
  selected,
  onSelect,
}: {
  position: Position;
  livePrice: number | null;
  selected: boolean;
  onSelect: (ticker: string) => void;
}) {
  const price = livePrice ?? position.current_price;
  const flash = usePriceFlash(price);

  // Revalue against the live price so P&L moves with the stream, not with polls.
  const marketValue = position.quantity * price;
  const pnl = marketValue - position.cost_basis;
  const pnlPercent = position.cost_basis !== 0 ? (pnl / position.cost_basis) * 100 : 0;

  return (
    <div
      data-testid={`position-row-${position.ticker}`}
      role="row"
      tabIndex={0}
      onClick={() => onSelect(position.ticker)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(position.ticker);
        }
      }}
      className={`grid ${COLUMNS} cursor-pointer items-center gap-2 border-l-2 px-3 py-1.5 text-[12px] transition-colors ${
        selected ? "border-l-accent bg-raised" : "border-l-transparent hover:bg-surface-2"
      }`}
    >
      <span className="num truncate font-semibold text-ink">{position.ticker}</span>
      <span data-testid={`position-quantity-${position.ticker}`} className="num text-right text-muted">
        {formatQuantity(position.quantity)}
      </span>
      <span data-testid={`position-avgcost-${position.ticker}`} className="num text-right text-muted">
        {formatPrice(position.avg_cost)}
      </span>
      <span
        data-testid={`position-price-${position.ticker}`}
        className={`num rounded px-1 text-right text-ink ${flashClass(flash)}`}
      >
        {formatPrice(price)}
      </span>
      <span data-testid={`position-pnl-${position.ticker}`} className={`num text-right ${signClass(pnl)}`}>
        {formatSignedMoney(pnl)}
      </span>
      <span
        data-testid={`position-pnlpct-${position.ticker}`}
        className={`num text-right ${signClass(pnlPercent)}`}
      >
        {formatPercent(pnlPercent)}
      </span>
    </div>
  );
}

export default function PositionsTable({
  positions,
  prices,
  selected,
  onSelect,
  loading,
}: PositionsTableProps) {
  const exposure = positions.reduce(
    (sum, p) => sum + p.quantity * (prices[p.ticker]?.price ?? p.current_price),
    0,
  );

  return (
    <Panel
      title="Positions"
      tick="var(--color-accent)"
      testId="positions-table"
      className="min-h-0 border-t border-line"
      bodyClassName="flex flex-col"
      right={<span className="num text-[11px] text-dim">{formatMoney(exposure)} exposure</span>}
    >
      <div
        className={`grid ${COLUMNS} gap-2 border-b border-line-soft px-3 py-1 text-[10px] text-dim`}
      >
        <span>Symbol</span>
        <span className="text-right">Qty</span>
        <span className="text-right">Avg cost</span>
        <span className="text-right">Last</span>
        <span className="text-right">Unrealized</span>
        <span className="text-right">Change</span>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading && positions.length === 0 ? (
          <p className="px-3 py-4 text-[12px] text-dim">Loading positions…</p>
        ) : positions.length === 0 ? (
          <p data-testid="positions-empty" className="px-3 py-5 text-center text-[12px] text-dim">
            No positions yet. Use the trade bar below, or ask the assistant to buy something.
          </p>
        ) : (
          positions.map((position) => (
            <PositionRow
              key={position.ticker}
              position={position}
              livePrice={prices[position.ticker]?.price ?? null}
              selected={selected === position.ticker}
              onSelect={onSelect}
            />
          ))
        )}
      </div>
    </Panel>
  );
}
