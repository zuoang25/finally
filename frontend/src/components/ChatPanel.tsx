"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, api } from "@/lib/api";
import { formatClock } from "@/lib/format";
import type { ChatAction, ChatMessage } from "@/lib/types";

interface ChatPanelProps {
  open: boolean;
  onActed: () => Promise<void> | void;
}

function ActionChip({ action }: { action: ChatAction }) {
  const failed = action.status === "failed";
  return (
    <span
      data-testid="chat-action"
      data-status={action.status}
      title={action.detail}
      className={`inline-flex max-w-full items-center gap-1.5 rounded-sm border px-1.5 py-0.5 text-[11px] ${
        failed
          ? "border-down/40 bg-down/10 text-down"
          : "border-up/40 bg-up/10 text-up"
      }`}
    >
      <span aria-hidden="true">{failed ? "✕" : "✓"}</span>
      <span className="num truncate">{action.detail}</span>
    </span>
  );
}

function Bubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div
      data-testid={isUser ? "chat-message-user" : "chat-message-assistant"}
      className={`flex flex-col gap-1.5 ${isUser ? "items-end" : "items-start"}`}
    >
      <div
        className={`max-w-[92%] whitespace-pre-wrap rounded-sm px-2.5 py-2 text-[12px] leading-relaxed ${
          isUser
            ? "bg-blue/15 text-ink ring-1 ring-inset ring-blue/30"
            : "bg-surface-2 text-ink ring-1 ring-inset ring-line"
        }`}
      >
        {message.content}
      </div>
      {message.actions && message.actions.length > 0 ? (
        <div className="flex max-w-[92%] flex-wrap gap-1">
          {message.actions.map((action, i) => (
            <ActionChip key={`${action.ticker}-${i}`} action={action} />
          ))}
        </div>
      ) : null}
      <span className="num text-[10px] text-dim">{formatClock(message.created_at)}</span>
    </div>
  );
}

export default function ChatPanel({ open, onActed }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const history = await api.getChatHistory();
        if (!cancelled) setMessages(history.messages ?? []);
      } catch {
        // A missing history is not worth a banner; the first send will surface real errors.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, sending]);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || sending) return;

    const optimistic: ChatMessage = {
      id: `local-${Date.now()}`,
      role: "user",
      content: text,
      actions: null,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimistic]);
    setDraft("");
    setSending(true);
    setError(null);

    try {
      const reply = await api.sendChat(text);
      setMessages((prev) => [
        ...prev,
        {
          id: `assistant-${reply.created_at}-${prev.length}`,
          role: "assistant",
          content: reply.message,
          actions: reply.actions ?? [],
          created_at: reply.created_at,
        },
      ]);
      if (reply.actions?.length) await onActed();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The assistant did not respond.");
    } finally {
      setSending(false);
    }
  }

  return (
    <aside
      id="chat-panel"
      data-testid="chat-panel"
      hidden={!open}
      className="flex h-full w-[340px] shrink-0 flex-col border-l border-line bg-surface"
    >
      <header className="flex h-8 shrink-0 items-center gap-2 border-b border-line px-3">
        <span
          className="h-3 w-[2px] shrink-0 rounded-full"
          style={{ background: "var(--color-purple)" }}
        />
        <h2 className="panel-title">Assistant</h2>
        <span className="ml-auto text-[11px] text-dim">executes trades directly</span>
      </header>

      <div
        ref={scrollRef}
        data-testid="chat-messages"
        className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-3"
      >
        {messages.length === 0 && !sending ? (
          <div className="m-auto max-w-[240px] text-center text-[12px] leading-relaxed text-dim">
            Ask about your book, or tell FinAlly what to trade — &ldquo;buy 5 NVDA&rdquo;,
            &ldquo;how concentrated am I?&rdquo;, &ldquo;add PYPL to my watchlist&rdquo;.
          </div>
        ) : (
          messages.map((message) => <Bubble key={message.id} message={message} />)
        )}

        {sending ? (
          <div data-testid="chat-loading" className="flex items-center gap-2 text-[12px] text-muted">
            <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-accent" />
            FinAlly is thinking…
          </div>
        ) : null}
      </div>

      {error ? (
        <p role="alert" className="border-t border-line px-3 py-2 text-[11px] text-down">
          {error}
        </p>
      ) : null}

      <form onSubmit={send} className="shrink-0 border-t border-line p-2">
        <div className="flex gap-1.5">
          <input
            data-testid="chat-input"
            aria-label="Message the assistant"
            placeholder="Ask or instruct…"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="min-w-0 flex-1 rounded-sm border border-line bg-ground px-2 py-1.5 text-[12px] text-ink placeholder:text-dim focus:border-blue focus:outline-none"
          />
          <button
            type="submit"
            data-testid="chat-send"
            disabled={sending}
            className="rounded-sm bg-purple px-3 py-1.5 text-[12px] font-semibold text-white transition hover:brightness-115 disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </form>
    </aside>
  );
}
