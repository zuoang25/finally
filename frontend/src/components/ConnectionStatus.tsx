import type { ConnectionState } from "@/lib/types";

const LABELS: Record<ConnectionState, string> = {
  connected: "Live",
  reconnecting: "Reconnecting",
  disconnected: "Offline",
};

const COLORS: Record<ConnectionState, string> = {
  connected: "var(--color-up)",
  reconnecting: "var(--color-accent)",
  disconnected: "var(--color-down)",
};

export default function ConnectionStatus({ state }: { state: ConnectionState }) {
  return (
    <div
      data-testid="connection-status"
      data-status={state}
      className="flex items-center gap-2 text-[11px] text-muted"
      title={`Market data ${LABELS[state].toLowerCase()}`}
    >
      <span
        className={`h-2 w-2 rounded-full ${state === "connected" ? "" : "pulse-dot"}`}
        style={{ background: COLORS[state], boxShadow: `0 0 8px ${COLORS[state]}` }}
      />
      {LABELS[state]}
    </div>
  );
}
