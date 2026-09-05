"use client";

import { useEffect, useMemo, useState } from "react";
import ChatPanel from "./ChatPanel";
import Header from "./Header";
import HeatmapPanel from "./HeatmapPanel";
import MainChart from "./MainChart";
import PnlChart from "./PnlChart";
import PositionsTable from "./PositionsTable";
import TradeBar from "./TradeBar";
import WatchlistPanel from "./WatchlistPanel";
import { usePriceStream } from "@/hooks/usePriceStream";
import { useTerminal } from "@/hooks/useTerminal";

export default function Terminal() {
  const { prices, series, connection } = usePriceStream();
  const { portfolio, watchlist, snapshots, loading, error, refresh } = useTerminal();
  const [selected, setSelected] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(true);

  // Follow the first watched symbol until the user picks one, and never leave a
  // removed symbol selected.
  useEffect(() => {
    if (watchlist.length === 0) return;
    setSelected((current) =>
      current && watchlist.some((w) => w.ticker === current) ? current : watchlist[0].ticker,
    );
  }, [watchlist]);

  const positions = portfolio?.positions ?? [];

  // The header and the P&L curve track live prices rather than the last poll.
  const live = useMemo(() => {
    if (!portfolio) return { total: null, pnl: null, pnlPercent: null };
    const marketValue = positions.reduce(
      (sum, p) => sum + p.quantity * (prices[p.ticker]?.price ?? p.current_price),
      0,
    );
    const pnl = marketValue - portfolio.total_cost_basis;
    return {
      total: portfolio.cash_balance + marketValue,
      pnl,
      pnlPercent: portfolio.total_cost_basis !== 0 ? (pnl / portfolio.total_cost_basis) * 100 : 0,
    };
  }, [portfolio, positions, prices]);

  const selectedItem = watchlist.find((w) => w.ticker === selected) ?? null;
  const selectedPrice = selected ? (prices[selected]?.price ?? selectedItem?.price ?? null) : null;
  const openPrice = selectedItem?.open_price ?? null;
  const dayChange = selectedPrice !== null && openPrice ? selectedPrice - openPrice : null;
  const dayChangePercent = dayChange !== null && openPrice ? (dayChange / openPrice) * 100 : null;

  return (
    <div data-testid="app-root" className="flex h-screen flex-col bg-ground text-ink">
      <Header
        totalValue={live.total ?? portfolio?.total_value ?? null}
        cashBalance={portfolio?.cash_balance ?? null}
        unrealizedPnl={live.pnl}
        unrealizedPnlPercent={live.pnlPercent}
        connection={connection}
        chatOpen={chatOpen}
        onToggleChat={() => setChatOpen((v) => !v)}
      />

      {error ? (
        <p role="alert" className="shrink-0 border-b border-down/40 bg-down/10 px-4 py-1.5 text-[12px] text-down">
          {error}
        </p>
      ) : null}

      <div className="flex min-h-0 flex-1">
        <div className="w-[296px] shrink-0">
          <WatchlistPanel
            items={watchlist}
            prices={prices}
            series={series}
            selected={selected}
            onSelect={setSelected}
            onChanged={refresh}
            loading={loading}
          />
        </div>

        <main className="flex min-h-0 flex-1 flex-col">
          <div className="min-h-0 flex-[7]">
            <MainChart
              ticker={selected}
              points={selected ? (series[selected] ?? []) : []}
              price={selectedPrice}
              dayChange={dayChange}
              dayChangePercent={dayChangePercent}
            />
          </div>

          <div className="grid min-h-0 flex-[5] grid-cols-2">
            <HeatmapPanel positions={positions} onSelect={setSelected} />
            <PnlChart snapshots={snapshots} liveTotal={live.total} />
          </div>

          <div className="min-h-0 flex-[5]">
            <PositionsTable
              positions={positions}
              prices={prices}
              selected={selected}
              onSelect={setSelected}
              loading={loading}
            />
          </div>

          <TradeBar ticker={selected} prices={prices} onTraded={refresh} />
        </main>

        <ChatPanel open={chatOpen} onActed={refresh} />
      </div>
    </div>
  );
}
