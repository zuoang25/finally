"use client";

import ConnectionStatus from "./ConnectionStatus";
import { formatMoney, formatPercent, formatSignedMoney, signClass } from "@/lib/format";
import type { ConnectionState } from "@/lib/types";

interface HeaderProps {
  totalValue: number | null;
  cashBalance: number | null;
  unrealizedPnl: number | null;
  unrealizedPnlPercent: number | null;
  connection: ConnectionState;
  chatOpen: boolean;
  onToggleChat: () => void;
}

function Stat({
  label,
  value,
  testId,
  className = "",
}: {
  label: string;
  value: string;
  testId?: string;
  className?: string;
}) {
  return (
    <div className="flex flex-col leading-tight">
      <span className="text-[10px] text-dim">{label}</span>
      <span data-testid={testId} className={`num text-[15px] font-semibold ${className}`}>
        {value}
      </span>
    </div>
  );
}

export default function Header({
  totalValue,
  cashBalance,
  unrealizedPnl,
  unrealizedPnlPercent,
  connection,
  chatOpen,
  onToggleChat,
}: HeaderProps) {
  return (
    <header className="flex h-14 shrink-0 items-center gap-6 border-b border-line bg-surface px-4">
      <div className="flex items-baseline gap-2">
        <span className="text-[17px] font-semibold tracking-tight text-ink">
          Fin<span style={{ color: "var(--color-accent)" }}>Ally</span>
        </span>
        <span className="hidden text-[11px] text-dim sm:inline">simulated book</span>
      </div>

      <div className="flex items-center gap-6">
        <Stat
          label="Total value"
          value={formatMoney(totalValue)}
          testId="header-total-value"
          className="text-ink"
        />
        <Stat label="Cash" value={formatMoney(cashBalance)} testId="header-cash-balance" />
        <Stat
          label="Unrealized"
          value={`${formatSignedMoney(unrealizedPnl)} (${formatPercent(unrealizedPnlPercent)})`}
          className={signClass(unrealizedPnl)}
        />
      </div>

      <div className="ml-auto flex items-center gap-4">
        <ConnectionStatus state={connection} />
        <button
          type="button"
          data-testid="chat-toggle"
          aria-expanded={chatOpen}
          aria-controls="chat-panel"
          onClick={onToggleChat}
          className="rounded-sm border border-line px-3 py-1.5 text-[12px] text-muted transition hover:border-blue hover:text-ink"
        >
          {chatOpen ? "Hide assistant" : "Show assistant"}
        </button>
      </div>
    </header>
  );
}
