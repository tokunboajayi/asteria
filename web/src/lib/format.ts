/** Number formatting. One place, so every panel shows a value the same way. */

export const MINUS = "−";

const intl = (digits: number) =>
  new Intl.NumberFormat("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });

/** Whole metres with thousands separators (the acceptance tests use this exact format). */
export function fmtM(value: number): string {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
}

export function fmtNum(value: number | null | undefined, digits: number): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  const text = intl(digits).format(Math.abs(value));
  return value < 0 ? MINUS + text : text;
}

export function fmtSigned(value: number | null | undefined, digits: number): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  const text = intl(digits).format(Math.abs(value));
  if (value > 0) return `+${text}`;
  if (value < 0) return MINUS + text;
  return text;
}

export function fmtPct(value: number | null | undefined, digits = 1): string {
  const text = fmtSigned(value, digits);
  return text === "—" ? text : `${text}%`;
}

export function fmtMet(seconds: number): string {
  const sign = seconds < 0 ? "−" : "+";
  const s = Math.abs(seconds);
  const mm = Math.floor(s / 60);
  const ss = s - mm * 60;
  return `T${sign} ${String(mm).padStart(2, "0")}:${ss.toFixed(1).padStart(4, "0")}`;
}

export function shortHash(hash: string, n = 7): string {
  return hash.slice(0, n);
}
