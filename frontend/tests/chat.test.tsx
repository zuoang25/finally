import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ChatPanel from "@/components/ChatPanel";
import Header from "@/components/Header";
import { ApiError } from "@/lib/api";
import type { ChatResponse } from "@/lib/types";
import { chatHistory } from "./fixtures";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { getChatHistory: vi.fn(), sendChat: vi.fn() } };
});

const { api } = await import("@/lib/api");
const getChatHistory = api.getChatHistory as unknown as ReturnType<typeof vi.fn>;
const sendChat = api.sendChat as unknown as ReturnType<typeof vi.fn>;

const reply: ChatResponse = {
  message: "Bought 5 NVDA at $138.20.",
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
  ],
  created_at: "2026-09-05T10:03:00Z",
};

/** A promise whose resolution the test controls, for asserting in-flight state. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

async function renderPanel(onActed = vi.fn()) {
  render(<ChatPanel open onActed={onActed} />);
  await waitFor(() => expect(getChatHistory).toHaveBeenCalled());
  return onActed;
}

describe("ChatPanel", () => {
  beforeEach(() => {
    getChatHistory.mockReset().mockResolvedValue({ messages: [] });
    sendChat.mockReset().mockResolvedValue(reply);
  });

  it("renders the contract testids", async () => {
    await renderPanel();
    expect(screen.getByTestId("chat-panel")).toBeInTheDocument();
    expect(screen.getByTestId("chat-messages")).toBeInTheDocument();
    expect(screen.getByTestId("chat-input")).toBeInTheDocument();
    expect(screen.getByTestId("chat-send")).toBeInTheDocument();
  });

  it("shows the empty-conversation prompt when there is no history", async () => {
    await renderPanel();
    expect(await screen.findByText(/Ask about your book/i)).toBeInTheDocument();
    expect(screen.queryByTestId("chat-message-user")).not.toBeInTheDocument();
    expect(screen.queryByTestId("chat-message-assistant")).not.toBeInTheDocument();
  });

  it("loads history and renders user and assistant bubbles distinctly", async () => {
    getChatHistory.mockResolvedValue({ messages: chatHistory });
    await renderPanel();

    const user = await screen.findByTestId("chat-message-user");
    expect(user).toHaveTextContent("buy me 5 nvidia");

    const assistant = screen.getByTestId("chat-message-assistant");
    expect(assistant).toHaveTextContent("Bought 5 NVDA at $138.20.");
    expect(screen.queryByText(/Ask about your book/i)).not.toBeInTheDocument();
  });

  it("renders one action chip per action, tagged with its status", async () => {
    getChatHistory.mockResolvedValue({ messages: chatHistory });
    await renderPanel();

    const chips = await screen.findAllByTestId("chat-action");
    expect(chips).toHaveLength(2);
    expect(chips[0]).toHaveAttribute("data-status", "executed");
    expect(chips[0]).toHaveTextContent("Bought 5 NVDA @ $138.20");
    expect(chips[1]).toHaveAttribute("data-status", "failed");
    expect(chips[1]).toHaveTextContent("Insufficient cash");
  });

  it("renders no chips for a message that carries no actions", async () => {
    getChatHistory.mockResolvedValue({ messages: [chatHistory[0]] });
    await renderPanel();
    await screen.findByTestId("chat-message-user");
    expect(screen.queryByTestId("chat-action")).not.toBeInTheDocument();
  });

  it("survives a failed history load and still accepts a message", async () => {
    getChatHistory.mockRejectedValue(new ApiError(500, "boom"));
    await renderPanel();

    expect(await screen.findByText(/Ask about your book/i)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    await userEvent.type(screen.getByTestId("chat-input"), "hello");
    await userEvent.click(screen.getByTestId("chat-send"));
    await waitFor(() => expect(sendChat).toHaveBeenCalledWith("hello"));
  });

  it("sends the trimmed draft, clears the input and appends both bubbles", async () => {
    await renderPanel();

    await userEvent.type(screen.getByTestId("chat-input"), "  buy me 5 nvidia  ");
    await userEvent.click(screen.getByTestId("chat-send"));

    await waitFor(() => expect(sendChat).toHaveBeenCalledWith("buy me 5 nvidia"));
    expect(screen.getByTestId("chat-input")).toHaveValue("");
    expect(screen.getByTestId("chat-message-user")).toHaveTextContent("buy me 5 nvidia");
    expect(await screen.findByTestId("chat-message-assistant")).toHaveTextContent(
      "Bought 5 NVDA at $138.20.",
    );
    const chip = await screen.findByTestId("chat-action");
    expect(chip).toHaveAttribute("data-status", "executed");
  });

  it("submits on Enter from the input", async () => {
    await renderPanel();
    await userEvent.type(screen.getByTestId("chat-input"), "how concentrated am I?{Enter}");
    await waitFor(() => expect(sendChat).toHaveBeenCalledWith("how concentrated am I?"));
  });

  it("ignores an empty or whitespace-only draft", async () => {
    await renderPanel();
    await userEvent.click(screen.getByTestId("chat-send"));
    await userEvent.type(screen.getByTestId("chat-input"), "   ");
    await userEvent.click(screen.getByTestId("chat-send"));
    expect(sendChat).not.toHaveBeenCalled();
  });

  it("shows the loading indicator only while a response is in flight", async () => {
    const pending = deferred<ChatResponse>();
    sendChat.mockReturnValue(pending.promise);
    await renderPanel();

    expect(screen.queryByTestId("chat-loading")).not.toBeInTheDocument();

    await userEvent.type(screen.getByTestId("chat-input"), "hello");
    await userEvent.click(screen.getByTestId("chat-send"));

    expect(await screen.findByTestId("chat-loading")).toBeInTheDocument();
    expect(screen.getByTestId("chat-send")).toBeDisabled();

    pending.resolve(reply);
    await waitFor(() => expect(screen.queryByTestId("chat-loading")).not.toBeInTheDocument());
    expect(screen.getByTestId("chat-send")).toBeEnabled();
  });

  it("does not send a second message while one is in flight", async () => {
    const pending = deferred<ChatResponse>();
    sendChat.mockReturnValue(pending.promise);
    await renderPanel();

    await userEvent.type(screen.getByTestId("chat-input"), "first");
    await userEvent.click(screen.getByTestId("chat-send"));
    await screen.findByTestId("chat-loading");

    await userEvent.type(screen.getByTestId("chat-input"), "second{Enter}");
    expect(sendChat).toHaveBeenCalledTimes(1);

    pending.resolve(reply);
    await waitFor(() => expect(screen.queryByTestId("chat-loading")).not.toBeInTheDocument());
  });

  it("refreshes the terminal when the turn executed actions", async () => {
    const onActed = await renderPanel();
    await userEvent.type(screen.getByTestId("chat-input"), "buy 5 NVDA{Enter}");
    await waitFor(() => expect(onActed).toHaveBeenCalled());
  });

  it("does not refresh when the turn executed nothing", async () => {
    sendChat.mockResolvedValue({ ...reply, actions: [] });
    const onActed = await renderPanel();

    await userEvent.type(screen.getByTestId("chat-input"), "how am I doing?{Enter}");
    expect(await screen.findByTestId("chat-message-assistant")).toBeInTheDocument();
    expect(onActed).not.toHaveBeenCalled();
    expect(screen.queryByTestId("chat-action")).not.toBeInTheDocument();
  });

  it("surfaces the backend detail when the assistant is unavailable", async () => {
    sendChat.mockRejectedValue(new ApiError(503, "AI assistant unavailable: no key"));
    await renderPanel();

    await userEvent.type(screen.getByTestId("chat-input"), "hello{Enter}");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("AI assistant unavailable: no key");
    // The optimistic user bubble stays; no assistant bubble is invented.
    expect(screen.getByTestId("chat-message-user")).toHaveTextContent("hello");
    expect(screen.queryByTestId("chat-message-assistant")).not.toBeInTheDocument();
    expect(screen.queryByTestId("chat-loading")).not.toBeInTheDocument();
  });

  it("falls back to a generic message for a non-API failure", async () => {
    sendChat.mockRejectedValue(new TypeError("nope"));
    await renderPanel();
    await userEvent.type(screen.getByTestId("chat-input"), "hello{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("The assistant did not respond.");
  });

  it("is hidden while collapsed and visible while open", async () => {
    const { rerender } = render(<ChatPanel open={false} onActed={vi.fn()} />);
    await waitFor(() => expect(getChatHistory).toHaveBeenCalled());
    expect(screen.getByTestId("chat-panel")).toHaveAttribute("hidden");

    rerender(<ChatPanel open onActed={vi.fn()} />);
    expect(screen.getByTestId("chat-panel")).not.toHaveAttribute("hidden");
  });
});

/** The toggle lives in the header but drives the panel, so exercise them together. */
function ChatHarness() {
  const [open, setOpen] = useState(true);
  return (
    <>
      <Header
        totalValue={10000}
        cashBalance={10000}
        unrealizedPnl={0}
        unrealizedPnlPercent={0}
        connection="connected"
        chatOpen={open}
        onToggleChat={() => setOpen((v) => !v)}
      />
      <ChatPanel open={open} onActed={vi.fn()} />
    </>
  );
}

describe("chat toggle", () => {
  beforeEach(() => {
    getChatHistory.mockReset().mockResolvedValue({ messages: [] });
    sendChat.mockReset().mockResolvedValue(reply);
  });

  it("collapses and re-expands the panel", async () => {
    render(<ChatHarness />);
    await waitFor(() => expect(getChatHistory).toHaveBeenCalled());

    const toggle = screen.getByTestId("chat-toggle");
    const panel = screen.getByTestId("chat-panel");
    expect(panel).not.toHaveAttribute("hidden");
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(toggle).toHaveTextContent("Hide assistant");

    await userEvent.click(toggle);
    expect(panel).toHaveAttribute("hidden");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(toggle).toHaveTextContent("Show assistant");

    await userEvent.click(toggle);
    expect(panel).not.toHaveAttribute("hidden");
    expect(toggle).toHaveTextContent("Hide assistant");
  });

  it("keeps the conversation mounted across a collapse", async () => {
    getChatHistory.mockResolvedValue({ messages: chatHistory });
    render(<ChatHarness />);

    await screen.findByTestId("chat-message-assistant");
    await userEvent.click(screen.getByTestId("chat-toggle"));

    const panel = screen.getByTestId("chat-panel");
    expect(within(panel).getByTestId("chat-message-assistant")).toBeInTheDocument();
    expect(getChatHistory).toHaveBeenCalledTimes(1);
  });
});
