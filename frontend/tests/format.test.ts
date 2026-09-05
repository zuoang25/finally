import { describe, expect, it } from "vitest";
import {
  formatClock,
  formatMoney,
  formatPercent,
  formatPrice,
  formatQuantity,
  formatSignedMoney,
  isValidTicker,
  normalizeTicker,
  signClass,
} from "@/lib/format";

describe("number formatting", () => {
  it("formats money with a currency symbol and two decimals", () => {
    expect(formatMoney(10000)).toBe("$10,000.00");
    expect(formatMoney(8050.5)).toBe("$8,050.50");
  });

  it("renders an em dash for unknown values", () => {
    expect(formatMoney(null)).toBe("—");
    expect(formatPrice(undefined)).toBe("—");
    expect(formatPercent(Number.NaN)).toBe("—");
    expect(formatQuantity(null)).toBe("—");
  });

  it("signs P&L amounts", () => {
    expect(formatSignedMoney(50)).toBe("+$50.00");
    expect(formatSignedMoney(-27.2)).toBe("-$27.20");
    expect(formatSignedMoney(0)).toBe("$0.00");
  });

  it("signs percentages", () => {
    expect(formatPercent(2.6316)).toBe("+2.63%");
    expect(formatPercent(-4.6897)).toBe("-4.69%");
    expect(formatPercent(0)).toBe("0.00%");
  });

  it("keeps integer share counts bare and trims fractional ones", () => {
    expect(formatQuantity(10)).toBe("10");
    expect(formatQuantity(2.5)).toBe("2.5");
    expect(formatQuantity(0.123456)).toBe("0.1235");
  });

  it("maps sign to colour classes", () => {
    expect(signClass(1)).toBe("text-up");
    expect(signClass(-1)).toBe("text-down");
    expect(signClass(0)).toBe("text-muted");
    expect(signClass(null)).toBe("text-muted");
  });

  it("formats an ISO timestamp as a 24h clock", () => {
    expect(formatClock("2026-09-05T10:02:00Z")).toMatch(/^\d{2}:\d{2}:\d{2}$/);
    expect(formatClock("nonsense")).toBe("");
  });
});

describe("ticker normalisation", () => {
  it("upper-cases and trims", () => {
    expect(normalizeTicker("  pypl ")).toBe("PYPL");
  });

  it("accepts the backend's symbol shape and rejects the rest", () => {
    expect(isValidTicker("aapl")).toBe(true);
    expect(isValidTicker("BRK.B")).toBe(true);
    expect(isValidTicker("")).toBe(false);
    expect(isValidTicker("1ABC")).toBe(false);
    expect(isValidTicker("TOOLONGSYMBOL")).toBe(false);
  });
});
