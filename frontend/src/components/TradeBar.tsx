"use client";

import { useEffect, useState } from "react";
import { ApiError, api } from "@/lib/api";
import { formatPrice, formatQuantity, isValidTicker, normalizeTicker } from "@/lib/format";
import type { PriceMap } from "@/lib/types";

interface TradeBarProps {
  /** Selected symbol, mirrored into the ticker field so a click pre-fills the order. */
  ticker: string | null;
  prices: PriceMap;
  onTraded: () => Promise<void> | void;
}

export default function TradeBar({ ticker, prices, onTraded }: TradeBarProps) {
  const [symbol, setSymbol] = useState(ticker ?? "");
  const [quantity, setQuantity] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [busy, setBusy] = useState<"buy" | "sell" | null>(null);

  useEffect(() => {
    if (ticker) setSymbol(ticker);
  }, [ticker]);

  const normalized = normalizeTicker(symbol);
  const quote = prices[normalized]?.price ?? null;
  const parsedQuantity = Number.parseFloat(quantity);
  const estimate =
    quote !== null && Number.isFinite(parsedQuantity) && parsedQuantity > 0
      ? quote * parsedQuantity
      : null;

  async function submit(side: "buy" | "sell") {
    setError(null);
    setSuccess(null);

    if (!isValidTicker(normalized)) {
      setError("Enter a symbol, for example AAPL.");
      return;
    }
    if (!Number.isFinite(parsedQuantity) || parsedQuantity <= 0) {
      setError("Enter a quantity greater than zero.");
      return;
    }

    setBusy(side);
    try {
      const result = await api.trade(normalized, parsedQuantity, side);
      const verb = side === "buy" ? "Bought" : "Sold";
      setSuccess(
        `${verb} ${formatQuantity(result.trade.quantity)} ${result.trade.ticker} at ${formatPrice(result.trade.price)}`,
      );
      setQuantity("");
      await onTraded();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : `Could not ${side} ${normalized}.`);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="shrink-0 border-t border-line bg-surface-2 px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="panel-title mr-1">Order</span>

        <input
          data-testid="trade-ticker-input"
          aria-label="Ticker to trade"
          placeholder="Symbol"
          value={symbol}
          maxLength={10}
          onChange={(e) => setSymbol(e.target.value.toUpperCase())}
          className="num w-24 rounded-sm border border-line bg-ground px-2 py-1.5 text-[12px] uppercase text-ink placeholder:font-sans placeholder:normal-case placeholder:text-dim focus:border-blue focus:outline-none"
        />

        <input
          data-testid="trade-quantity-input"
          aria-label="Quantity to trade"
          placeholder="Qty"
          inputMode="decimal"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          className="num w-24 rounded-sm border border-line bg-ground px-2 py-1.5 text-right text-[12px] text-ink placeholder:font-sans placeholder:text-dim focus:border-blue focus:outline-none"
        />

        <button
          type="button"
          data-testid="trade-buy-button"
          disabled={busy !== null}
          onClick={() => submit("buy")}
          className="rounded-sm bg-up/15 px-4 py-1.5 text-[12px] font-semibold text-up ring-1 ring-inset ring-up/40 transition hover:bg-up/25 disabled:opacity-50"
        >
          {busy === "buy" ? "Buying…" : "Buy"}
        </button>

        <button
          type="button"
          data-testid="trade-sell-button"
          disabled={busy !== null}
          onClick={() => submit("sell")}
          className="rounded-sm bg-down/15 px-4 py-1.5 text-[12px] font-semibold text-down ring-1 ring-inset ring-down/40 transition hover:bg-down/25 disabled:opacity-50"
        >
          {busy === "sell" ? "Selling…" : "Sell"}
        </button>

        <span className="num ml-auto text-[11px] text-dim">
          {quote !== null ? `Last ${formatPrice(quote)}` : "No live quote"}
          {estimate !== null ? ` · est. ${formatPrice(estimate)}` : ""}
        </span>
      </div>

      {error ? (
        <p data-testid="trade-error" role="alert" className="mt-1.5 text-[11px] text-down">
          {error}
        </p>
      ) : null}
      {success ? (
        <p data-testid="trade-success" role="status" className="mt-1.5 text-[11px] text-up">
          {success}
        </p>
      ) : null}
    </div>
  );
}
