/**
 * Plot geometry for the strip charts and gap map. Pure functions, no DOM.
 * A null sample breaks the line: nothing is ever drawn where there is no data.
 */

export interface Domain {
  min: number;
  max: number;
}

/** Min/max over every finite value; null when a series set has no data at all. */
export function extent(series: readonly (readonly (number | null)[])[]): Domain | null {
  let min = Infinity;
  let max = -Infinity;
  for (const s of series) {
    for (const v of s) {
      if (v === null || !Number.isFinite(v)) continue;
      if (v < min) min = v;
      if (v > max) max = v;
    }
  }
  return Number.isFinite(min) ? { min, max } : null;
}

/** Pad a domain by a fraction of its span (or ±1 when flat) so lines never touch the edge. */
export function padded(d: Domain, fraction = 0.06): Domain {
  const span = d.max - d.min;
  const pad = span > 0 ? span * fraction : 1;
  return { min: d.min - pad, max: d.max + pad };
}

/** Symmetric domain around zero, for residual charts. */
export function symmetric(d: Domain): Domain {
  const m = Math.max(Math.abs(d.min), Math.abs(d.max)) || 1;
  return { min: -m, max: m };
}

export function scale(d: Domain, from: number, to: number) {
  const span = d.max - d.min || 1;
  return (v: number) => from + ((v - d.min) / span) * (to - from);
}

/** SVG path "d" for (t, v) pairs; each null starts a new sub-path. */
export function linePath(
  t: readonly number[],
  v: readonly (number | null)[],
  x: (n: number) => number,
  y: (n: number) => number,
): string {
  const parts: string[] = [];
  let pen = false;
  for (let i = 0; i < t.length; i++) {
    const value = v[i];
    if (value === null || value === undefined || !Number.isFinite(value)) {
      pen = false;
      continue;
    }
    parts.push(`${pen ? "L" : "M"}${x(t[i]).toFixed(2)},${y(value).toFixed(2)}`);
    pen = true;
  }
  return parts.join("");
}

/** Clamp to [min, max]. */
export function clamp(v: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, v));
}
