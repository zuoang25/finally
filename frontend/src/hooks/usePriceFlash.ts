"use client";

import { useEffect, useRef, useState } from "react";

export type FlashState = "up" | "down" | null;

/** How long the green/red highlight lingers before fading out. */
export const FLASH_MS = 500;

/**
 * Returns "up" / "down" for FLASH_MS after `price` changes, so a cell can
 * paint a brief highlight. Null between changes and on first render.
 */
export function usePriceFlash(price: number | null | undefined, duration = FLASH_MS): FlashState {
  const [flash, setFlash] = useState<FlashState>(null);
  const previous = useRef<number | null | undefined>(price);

  useEffect(() => {
    const prev = previous.current;
    previous.current = price;
    if (typeof price !== "number" || typeof prev !== "number" || price === prev) return;

    setFlash(price > prev ? "up" : "down");
    const timer = setTimeout(() => setFlash(null), duration);
    return () => clearTimeout(timer);
  }, [price, duration]);

  return flash;
}

/** Tailwind classes for a flashing cell. */
export function flashClass(flash: FlashState): string {
  if (flash === "up") return "flash-up";
  if (flash === "down") return "flash-down";
  return "";
}
