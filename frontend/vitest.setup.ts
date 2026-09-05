import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
});

// jsdom has no ResizeObserver; chart wrappers observe their container.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = globalThis.ResizeObserver ?? (ResizeObserverStub as never);

// jsdom has no EventSource. Tests that need one install their own fake.
if (!("EventSource" in globalThis)) {
  class EventSourceStub {
    static readonly CONNECTING = 0;
    static readonly OPEN = 1;
    static readonly CLOSED = 2;
    onmessage: ((e: MessageEvent) => void) | null = null;
    onerror: ((e: Event) => void) | null = null;
    onopen: ((e: Event) => void) | null = null;
    readyState = 0;
    close() {
      this.readyState = 2;
    }
  }
  globalThis.EventSource = EventSourceStub as never;
}

// Charts render to canvas, which jsdom does not implement.
globalThis.HTMLCanvasElement.prototype.getContext = vi.fn(() => null) as never;
