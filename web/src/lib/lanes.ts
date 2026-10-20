/**
 * Place text labels on a horizontal axis without overlap: each label goes in
 * the first lane where it clears the previous label; when every lane is full
 * it is left out (its marker line still shows, and the timeline lists it).
 */
export interface Placed<T> {
  item: T;
  lane: number;
}

export function assignLanes<T>(
  items: readonly T[],
  xPx: (item: T) => number,
  widthPx: (item: T) => number,
  maxLanes: number,
  gapPx = 6,
): Placed<T>[] {
  const ends: number[] = [];
  const out: Placed<T>[] = [];
  const sorted = [...items].sort((a, b) => xPx(a) - xPx(b));
  for (const item of sorted) {
    const x = xPx(item);
    let lane = ends.findIndex((end) => x >= end + gapPx);
    if (lane === -1 && ends.length < maxLanes) lane = ends.length;
    if (lane === -1) continue;
    ends[lane] = x + widthPx(item);
    out.push({ item, lane });
  }
  return out;
}

/** Width of a monospace label: characters × advance (IBM Plex Mono advance is 0.6 em). */
export function monoWidth(text: string, fontPx: number): number {
  return text.length * fontPx * 0.6;
}
