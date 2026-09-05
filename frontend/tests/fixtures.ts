import type {
  ChatMessage,
  Portfolio,
  PriceMap,
  Snapshot,
  WatchlistItem,
} from "@/lib/types";

export const watchlist: WatchlistItem[] = [
  {
    ticker: "AAPL",
    price: 190.5,
    previous_price: 190.42,
    open_price: 190.0,
    change: 0.5,
    change_percent: 0.263,
    direction: "up",
    added_at: "2026-09-05T10:00:00Z",
  },
  {
    ticker: "NVDA",
    price: 138.2,
    previous_price: 138.9,
    open_price: 140.0,
    change: -1.8,
    change_percent: -1.2857,
    direction: "down",
    added_at: "2026-09-05T10:00:01Z",
  },
  {
    ticker: "PYPL",
    price: null,
    previous_price: null,
    open_price: null,
    change: null,
    change_percent: null,
    direction: "flat",
    added_at: "2026-09-05T10:00:02Z",
  },
];

export const portfolio: Portfolio = {
  cash_balance: 8050,
  positions: [
    {
      ticker: "AAPL",
      quantity: 10,
      avg_cost: 190,
      current_price: 195,
      market_value: 1950,
      cost_basis: 1900,
      unrealized_pnl: 50,
      unrealized_pnl_percent: 2.6316,
      weight: 19.5,
    },
    {
      ticker: "NVDA",
      quantity: 4,
      avg_cost: 145,
      current_price: 138.2,
      market_value: 552.8,
      cost_basis: 580,
      unrealized_pnl: -27.2,
      unrealized_pnl_percent: -4.6897,
      weight: 5.5,
    },
  ],
  positions_value: 2502.8,
  total_value: 10552.8,
  total_cost_basis: 2480,
  total_unrealized_pnl: 22.8,
  total_unrealized_pnl_percent: 0.9194,
};

export const emptyPortfolio: Portfolio = {
  cash_balance: 10000,
  positions: [],
  positions_value: 0,
  total_value: 10000,
  total_cost_basis: 0,
  total_unrealized_pnl: 0,
  total_unrealized_pnl_percent: 0,
};

export const snapshots: Snapshot[] = [
  { total_value: 10000, recorded_at: "2026-09-05T10:00:00Z" },
  { total_value: 10120.5, recorded_at: "2026-09-05T10:00:30Z" },
  { total_value: 10552.8, recorded_at: "2026-09-05T10:01:00Z" },
];

export const prices: PriceMap = {
  AAPL: {
    ticker: "AAPL",
    price: 195,
    previous_price: 194.5,
    timestamp: 1757030400,
    change: 0.5,
    change_percent: 0.257,
    direction: "up",
  },
  NVDA: {
    ticker: "NVDA",
    price: 138.2,
    previous_price: 138.9,
    timestamp: 1757030400,
    change: -0.7,
    change_percent: -0.504,
    direction: "down",
  },
};

export const chatHistory: ChatMessage[] = [
  {
    id: "m1",
    role: "user",
    content: "buy me 5 nvidia",
    actions: null,
    created_at: "2026-09-05T10:02:00Z",
  },
  {
    id: "m2",
    role: "assistant",
    content: "Bought 5 NVDA at $138.20.",
    actions: [
      {
        type: "trade",
        status: "executed",
        ticker: "NVDA",
        side: "buy",
        quantity: 5,
        price: 138.2,
        detail: "Bought 5 NVDA @ $138.20",
      },
      {
        type: "trade",
        status: "failed",
        ticker: "TSLA",
        side: "buy",
        quantity: 1000,
        price: null,
        detail: "Insufficient cash: need $250000.00, have $8050.00",
      },
    ],
    created_at: "2026-09-05T10:02:01Z",
  },
];
