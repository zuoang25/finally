"use client";

import { useMemo } from "react";
import LineChart from "./LineChart";
import Panel from "./Panel";
import { formatPercent, formatSignedMoney, signClass } from "@/lib/format";
import type { Snapshot } from "@/lib/types";

interface PnlChartProps {
  snapshots: Snapshot[];
  /** Live total, appended as the trailing point so the line tracks the header. */
  liveTotal: number | null;
}

export default function PnlChart({ snapshots, liveTotal }: PnlChartProps) {
  const points = useMemo(() => {
    const mapped = snapshots
      .map((s) => ({ time: Date.parse(s.recorded_at) / 1000, value: s.total_value }))
      .filter((p) => Number.isFinite(p.time));
    if (liveTotal !== null && Number.isFinite(liveTotal)) {
      mapped.push({ time: Date.now() / 1000, value: liveTotal });
    }
    return mapped;
  }, [snapshots, liveTotal]);

  const first = points[0]?.value ?? null;
  const last = points[points.length - 1]?.value ?? null;
  const delta = first !== null && last !== null ? last - first : null;
  const deltaPercent = delta !== null && first ? (delta / first) * 100 : null;

  return (
    <Panel
      title="Portfolio value"
      tick="var(--color-purple)"
      testId="pnl-chart"
      className="min-h-0 border-l border-line"
      bodyClassName="relative"
      right={
        <span className={`num text-[11px] ${signClass(delta)}`}>
          {formatSignedMoney(delta)}{" "}
          {deltaPercent === null ? "" : `(${formatPercent(deltaPercent)})`}
        </span>
      }
    >
      <div className="absolute inset-0">
        {points.length >= 2 ? (
          <LineChart points={points} color={(delta ?? 0) >= 0 ? "#209dd7" : "#ff5c6c"} precision={2} />
        ) : (
          <div className="flex h-full items-center justify-center px-4 text-center text-[12px] text-dim">
            Portfolio value is recorded every 30 seconds. The curve appears once there are two
            snapshots.
          </div>
        )}
      </div>
    </Panel>
  );
}
