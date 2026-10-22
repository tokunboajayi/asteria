"use client";

import type { FleetFingerprint } from "@/lib/api";
import { fmtNum, fmtPct } from "@/lib/format";
import { monoWidth } from "@/lib/lanes";
import type { Loadable } from "@/lib/useApi";

import styles from "./Analysis.module.css";
import { PanelStatus } from "./PanelStatus";
import panels from "./Panels.module.css";

interface Props {
  fingerprint: Loadable<FleetFingerprint>;
  flightId: string;
}

// Plot geometry in SVG units. The SVG scales to the panel width; 270 units is narrower
// than any panel, so text is never drawn smaller than its stated size.
const W = 270;
const H = 200;
const M = { left: 40, right: 10, top: 10, bottom: 36 };
const LABEL_PX = 11;
const LABEL_GAP = 7;
const LINE = LABEL_PX + 3;

interface Point {
  id: string;
  name: string;
  x: number; // burn ratio
  y: number; // coast drag ratio
}

/** Domain that always shows 1.0 and every point, padded, in round 0.05 steps. */
function domain(values: number[]): [number, number] {
  const lo = Math.min(0.9, ...values) - 0.03;
  const hi = Math.max(1.1, ...values) + 0.03;
  return [Math.floor(lo * 20) / 20, Math.ceil(hi * 20) / 20];
}

function ticks([lo, hi]: [number, number]): number[] {
  const out: number[] = [];
  for (let v = Math.ceil(lo * 10) / 10; v <= hi + 1e-9; v += 0.1) out.push(Math.round(v * 10) / 10);
  return out;
}

/**
 * Fleet fingerprint: each accelerometer flight placed by what its sensor measured,
 * real ÷ ghost — speed gained in the burn (x) against drag in early coast (y).
 */
export function FingerprintPanel({ fingerprint, flightId }: Props) {
  if (fingerprint.state !== "ready") return <PanelStatus title="Motor & drag fingerprint" state={fingerprint} />;
  const fp = fingerprint.data;
  const points: Point[] = fp.rows.flatMap((r) =>
    r.fingerprint.status === "measured" && r.fingerprint.burn_ratio !== null && r.fingerprint.coast_drag_ratio !== null
      ? [{ id: r.id, name: r.name, x: r.fingerprint.burn_ratio, y: r.fingerprint.coast_drag_ratio }]
      : [],
  );
  const missing = fp.rows.filter((r) => r.fingerprint.status !== "measured");
  const mine = fp.rows.find((r) => r.id === flightId);
  const xd = domain(points.map((p) => p.x));
  const yd = domain(points.map((p) => p.y));
  const sx = (v: number) => M.left + ((v - xd[0]) / (xd[1] - xd[0])) * (W - M.left - M.right);
  const sy = (v: number) => H - M.bottom - ((v - yd[0]) / (yd[1] - yd[0])) * (H - M.top - M.bottom);
  const labels = placeLabels(points, sx, sy);

  return (
    <section className={panels.panel} aria-labelledby="fingerprint-title">
      <div className={panels.head}>
        <h2 id="fingerprint-title" className="label">
          Motor & drag fingerprint
        </h2>
        <span className={panels.tagNeutral}>Measured</span>
      </div>
      <p className={panels.lead}>
        What each flight&apos;s accelerometer felt, divided by what the ghost&apos;s sensor felt: speed gained in
        the burn, and drag in early coast.
      </p>
      {points.length > 0 && (
        <div className={styles.plot} data-testid="fingerprint-plot">
          <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Burn ratio against coast drag ratio, per flight">
            {ticks(xd).map((v) => (
              <text key={`x${v}`} x={sx(v)} y={H - M.bottom + 14} textAnchor="middle" className={styles.tick}>
                {fmtNum(v, 1)}
              </text>
            ))}
            {ticks(yd).map((v) => (
              <text key={`y${v}`} x={M.left - 6} y={sy(v) + 4} textAnchor="end" className={styles.tick}>
                {fmtNum(v, 1)}
              </text>
            ))}
            <line x1={M.left} x2={W - M.right} y1={H - M.bottom} y2={H - M.bottom} className={styles.axisLine} />
            <line x1={M.left} x2={M.left} y1={M.top} y2={H - M.bottom} className={styles.axisLine} />
            <line x1={sx(1)} x2={sx(1)} y1={M.top} y2={H - M.bottom} className={styles.unity} />
            <line x1={M.left} x2={W - M.right} y1={sy(1)} y2={sy(1)} className={styles.unity} />
            <text x={(M.left + W - M.right) / 2} y={H - 4} textAnchor="middle" className={styles.axisTitle}>
              Burn, real ÷ ghost →
            </text>
            {points.map((p) => (
              <circle
                key={p.id}
                cx={sx(p.x)}
                cy={sy(p.y)}
                r={p.id === flightId ? 6 : 5}
                className={p.id === flightId ? styles.pointMine : styles.point}
              >
                <title>
                  {p.name}: burn {fmtNum(p.x, 2)}×, coast drag {fmtNum(p.y, 2)}×
                </title>
              </circle>
            ))}
            {labels.map((l) => (
              <text
                key={l.id}
                x={l.x}
                y={l.y}
                textAnchor={l.anchor}
                className={l.id === flightId ? styles.pointLabelMine : styles.pointLabel}
              >
                {l.text}
              </text>
            ))}
          </svg>
          <p className={panels.note}>
            ↑ Coast drag, real ÷ ghost. Dashed lines mark 1.0, where the flight matched the ghost. Right of
            the line, the real burn added more speed; above it, the real rocket felt more drag.
          </p>
        </div>
      )}

      {mine && (
        <dl className={panels.kv} data-testid="fingerprint-mine">
          {mine.fingerprint.status === "measured" ? (
            <>
              <dt>Burn · speed gained</dt>
              <dd>
                {fmtNum(mine.fingerprint.burn_gain_real_mps, 0)} vs {fmtNum(mine.fingerprint.burn_gain_ghost_mps, 0)} m/s
                · {fmtNum(mine.fingerprint.burn_ratio, 2)}×
              </dd>
              <dt>Coast · drag deceleration</dt>
              <dd>
                {fmtNum(-(mine.fingerprint.coast_decel_real_mps2 ?? 0), 1)} vs{" "}
                {fmtNum(-(mine.fingerprint.coast_decel_ghost_mps2 ?? 0), 1)} m/s² ·{" "}
                {fmtNum(mine.fingerprint.coast_drag_ratio, 2)}×
              </dd>
              <dt>Apogee error (ghost)</dt>
              <dd>{fmtPct(mine.ghost_error_pct)}</dd>
            </>
          ) : (
            <>
              <dt>This flight</dt>
              <dd>Not measured</dd>
            </>
          )}
        </dl>
      )}
      {mine && mine.fingerprint.status !== "measured" && <p className={panels.note}>{mine.fingerprint.reason}</p>}
      {missing.length > 0 && (
        <p className={panels.note}>
          Not measured ({missing.length} of {fp.rows.length}): {missing.map((r) => r.name).join(", ")}. No
          accelerometer, or one whose zero could not be verified.
        </p>
      )}
      <details className={panels.note}>
        <summary className="label">How this is measured</summary>
        <p>{fp.method}</p>
        <p>{fp.not_attempted}</p>
      </details>
    </section>
  );
}

interface Label {
  id: string;
  text: string;
  x: number;
  y: number;
  anchor: "start" | "end";
}

/** Names beside their points, flipped left near the edge and pushed apart vertically. */
function placeLabels(points: Point[], sx: (v: number) => number, sy: (v: number) => number): Label[] {
  const placed: Label[] = [];
  const sorted = [...points].sort((a, b) => sy(a.y) - sy(b.y));
  for (const p of sorted) {
    const width = monoWidth(p.name, LABEL_PX);
    const right = sx(p.x) + LABEL_GAP + width <= W - M.right;
    let y = sy(p.y) + 4;
    const x = right ? sx(p.x) + LABEL_GAP : sx(p.x) - LABEL_GAP;
    const span = (l: { x: number; anchor: "start" | "end"; text: string }) => {
      const w = monoWidth(l.text, LABEL_PX);
      return l.anchor === "start" ? [l.x, l.x + w] : [l.x - w, l.x];
    };
    const mine = span({ x, anchor: right ? "start" : "end", text: p.name });
    for (const other of placed) {
      const [a0, a1] = span(other);
      const overlapX = mine[0] < a1 && a0 < mine[1];
      if (overlapX && Math.abs(other.y - y) < LINE) y = other.y + LINE;
    }
    placed.push({ id: p.id, text: p.name, x, y, anchor: right ? "start" : "end" });
  }
  return placed;
}
