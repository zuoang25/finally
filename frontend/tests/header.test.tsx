import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import ConnectionStatus from "@/components/ConnectionStatus";
import Header from "@/components/Header";
import type { ConnectionState } from "@/lib/types";

function renderHeader(overrides: Partial<Parameters<typeof Header>[0]> = {}) {
  const props = {
    totalValue: 10552.8,
    cashBalance: 8050,
    unrealizedPnl: 22.8,
    unrealizedPnlPercent: 0.9194,
    connection: "connected" as ConnectionState,
    chatOpen: true,
    onToggleChat: vi.fn(),
    ...overrides,
  };
  render(<Header {...props} />);
  return props;
}

describe("Header", () => {
  it("formats the live total and cash balance as money", () => {
    renderHeader();
    expect(screen.getByTestId("header-total-value")).toHaveTextContent("$10,552.80");
    expect(screen.getByTestId("header-cash-balance")).toHaveTextContent("$8,050.00");
  });

  it("shows an em dash before the first portfolio load", () => {
    renderHeader({ totalValue: null, cashBalance: null, unrealizedPnl: null });
    expect(screen.getByTestId("header-total-value")).toHaveTextContent("—");
    expect(screen.getByTestId("header-cash-balance")).toHaveTextContent("—");
  });

  it("renders unrealized P&L signed, with its percentage, coloured green", () => {
    renderHeader();
    const stat = screen.getByText(/\+\$22\.80/);
    expect(stat).toHaveTextContent("(+0.92%)");
    expect(stat.className).toContain("text-up");
  });

  it("colours a losing book red", () => {
    renderHeader({ unrealizedPnl: -27.2, unrealizedPnlPercent: -4.6897 });
    const stat = screen.getByText(/-\$27\.20/);
    expect(stat).toHaveTextContent("(-4.69%)");
    expect(stat.className).toContain("text-down");
  });

  it("stays neutral at a flat P&L", () => {
    renderHeader({ unrealizedPnl: 0, unrealizedPnlPercent: 0 });
    const stat = screen.getByText(/\$0\.00/);
    expect(stat.className).toContain("text-muted");
  });

  it("toggles the assistant and reflects the state on the button", async () => {
    const props = renderHeader({ chatOpen: false });
    const toggle = screen.getByTestId("chat-toggle");
    expect(toggle).toHaveTextContent("Show assistant");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(toggle).toHaveAttribute("aria-controls", "chat-panel");

    await userEvent.click(toggle);
    expect(props.onToggleChat).toHaveBeenCalledTimes(1);
  });

  it("carries the connection state through to the status dot", () => {
    renderHeader({ connection: "reconnecting" });
    expect(screen.getByTestId("connection-status")).toHaveAttribute("data-status", "reconnecting");
  });
});

describe("ConnectionStatus", () => {
  const cases: Array<[ConnectionState, string]> = [
    ["connected", "Live"],
    ["reconnecting", "Reconnecting"],
    ["disconnected", "Offline"],
  ];

  for (const [state, label] of cases) {
    it(`renders data-status="${state}" with the ${label} label`, () => {
      render(<ConnectionStatus state={state} />);
      const el = screen.getByTestId("connection-status");
      expect(el).toHaveAttribute("data-status", state);
      expect(el).toHaveTextContent(label);
      expect(el).toHaveAttribute("title", `Market data ${label.toLowerCase()}`);
    });
  }

  it("pulses only when the stream is not healthy", () => {
    const { rerender } = render(<ConnectionStatus state="connected" />);
    const dot = () => screen.getByTestId("connection-status").querySelector("span");
    expect(dot()?.className).not.toContain("pulse-dot");

    rerender(<ConnectionStatus state="disconnected" />);
    expect(dot()?.className).toContain("pulse-dot");
  });
});
