/** Time-series helpers. No smoothing, no extrapolation: outside the data, the answer is null. */

/** Index of the last element <= x (binary search); -1 if x is before the start. */
function floorIndex(t: readonly number[], x: number): number {
  let lo = 0;
  let hi = t.length - 1;
  if (t.length === 0 || x < t[0]) return -1;
  if (x >= t[hi]) return hi;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (t[mid] <= x) lo = mid;
    else hi = mid;
  }
  return lo;
}

/** Linear interpolation of v at x; null outside [t0, tN] or next to a null sample. */
export function interpAt(t: readonly number[], v: readonly (number | null)[], x: number): number | null {
  const i = floorIndex(t, x);
  if (i < 0 || x > t[t.length - 1]) return null;
  const a = v[i];
  if (i === t.length - 1 || t[i] === x) return a ?? null;
  const b = v[i + 1];
  if (a === null || a === undefined || b === null || b === undefined) return null;
  const f = (x - t[i]) / (t[i + 1] - t[i]);
  return a + f * (b - a);
}

/** Resample `v(t)` onto `grid`, null outside the source span. */
export function resample(t: readonly number[], v: readonly (number | null)[], grid: readonly number[]) {
  return grid.map((x) => interpAt(t, v, x));
}

export function shiftTime(t: readonly number[], shift: number): number[] {
  return t.map((x) => x + shift);
}
