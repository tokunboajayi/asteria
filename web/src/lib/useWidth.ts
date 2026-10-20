"use client";

import { useEffect, useState, type RefObject } from "react";

/** Live content width of an element (0 until measured). */
export function useWidth(ref: RefObject<Element | null>): number {
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => setWidth(entries[0]?.contentRect.width ?? 0));
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref]);
  return width;
}
