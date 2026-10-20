"use client";

import type { GapCell, GapMap } from "@/lib/api";
import { fmtNum, fmtSigned } from "@/lib/format";
import type { Loadable } from "@/lib/useApi";

import { PanelStatus } from "./PanelStatus";
import styles from "./Panels.module.css";

const SLOWER = "255, 176, 32"; // --gap: real slower than the ghost
const FASTER = "95, 180, 255"; // --ghost: real faster than the ghost

interface Props {
  gap: Loadable<GapMap>;
  flightId: string;
}

/** Where across the envelope the ghost and the logs disagree; empty where there is no evidence. */
export function GapMapPanel({ gap, flightId }: Props) {
  if (gap.state !== "ready") return <PanelStatus title="Reality gap map" state={gap} />;
  const g = gap.data;
  const nx = g.x_edges.length - 1;
  const ny = g.y_edges.length - 1;
  const byIndex = new Map(g.cells.map((c) => [`${c.x_index},${c.y_index}`, c]));
  const charted = g.cells.filter((c) => c.charted && c.mean !== null);
  const maxAbs = Math.max(1e-9, ...charted.map((c) => Math.abs(c.mean as number)));
  const strongest = charted.reduce<GapCell | null>(
    (best, c) => (best === null || Math.abs(c.mean as number) > Math.abs(best.mean as number) ? c : best),
    null,
  );
  const rows: GapCell[][] = [];
  for (let j = ny - 1; j >= 0; j--) {
    const row: GapCell[] = [];
    for (let i = 0; i < nx; i++) {
      const cell = byIndex.get(`${i},${j}`);
      if (cell) row.push(cell);
    }
    rows.push(row);
  }
  const range = (edges: number[], k: number, digits: number) =>
    `${fmtNum(edges[k], digits)}–${fmtNum(edges[k + 1], digits)}`;

  return (
    <section className={styles.panel} aria-labelledby="gapmap-title">
      <div className={styles.head}>
        <h2 id="gapmap-title" className="label">
          Reality gap map
        </h2>
        <span className={styles.tagNeutral}>
          {g.flights_included.length} flights · {charted.length} cells
        </span>
      </div>
      <p className={styles.note}>
        {g.quantity} ({g.unit}). {g.coordinates}. A cell needs logs from at least {g.min_flights} flights;
        fewer, and it stays empty.
      </p>
      <div className={styles.mapWrap}>
        <div className={styles.yAxis} aria-hidden="true">
          <span>{fmtNum(g.y_edges[ny], 0)} m</span>
          <span>0 m</span>
        </div>
        <div
          role="img"
          aria-label={`Reality gap map: ${g.quantity} across ${g.x_label} and ${g.y_label}. ${charted.length} charted cells${
            strongest
              ? `; largest mean gap ${fmtSigned(strongest.mean, 1)} ${g.unit} at Mach ${range(g.x_edges, strongest.x_index, 1)}, ${range(g.y_edges, strongest.y_index, 0)} m`
              : ""
          }.`}
          className={styles.map}
          style={{ gridTemplateColumns: `repeat(${nx}, minmax(0, 1fr))`, flex: 1 }}
        >
          {rows.flat().map((c) => (
            <div
              key={`${c.x_index},${c.y_index}`}
              data-charted={c.charted ? "true" : "false"}
              title={cellTitle(c, g)}
              className={[
                styles.cell,
                c.charted ? "" : c.reachable ? styles.uncharted : styles.unreached,
                c.ghost_flights.includes(flightId) ? styles.mine : "",
              ].join(" ")}
              style={c.charted && c.mean !== null ? { background: colour(c.mean, maxAbs) } : undefined}
            />
          ))}
        </div>
      </div>
      <div className={styles.axis} aria-hidden="true" style={{ paddingLeft: 40 }}>
        <span>M {fmtNum(g.x_edges[0], 1)}</span>
        <span>{g.x_label}</span>
        <span>M {fmtNum(g.x_edges[nx], 1)}</span>
      </div>
      <div className={styles.legendRow}>
        <span>real faster</span>
        <span
          className={styles.ramp}
          aria-hidden="true"
          style={{ background: `linear-gradient(90deg, rgb(${FASTER}), #1a1f27, rgb(${SLOWER}))` }}
        />
        <span>real slower</span>
        <span>
          <span className={`${styles.key} ${styles.uncharted}`} aria-hidden="true" />
          flown, not enough logs
        </span>
        <span>
          <span className={`${styles.key} ${styles.mine}`} aria-hidden="true" />
          this flight&apos;s ghost
        </span>
      </div>
      <ul className={styles.caveats}>
        {g.caveats.map((c) => (
          <li key={c}>{c}</li>
        ))}
      </ul>
    </section>
  );
}

function colour(mean: number, maxAbs: number): string {
  const f = Math.min(1, Math.abs(mean) / maxAbs);
  const rgb = mean < 0 ? SLOWER : FASTER;
  return `rgba(${rgb}, ${(0.15 + 0.85 * f).toFixed(3)})`;
}

function cellTitle(c: GapCell, g: GapMap): string {
  const where = `Mach ${g.x_edges[c.x_index]}–${g.x_edges[c.x_index + 1]}, ${g.y_edges[c.y_index]}–${g.y_edges[c.y_index + 1]} m`;
  if (c.charted) {
    return `${where}: mean ${fmtSigned(c.mean, 1)} ${g.unit}, std ${fmtNum(c.std, 1)}, ${c.n_samples} samples from ${c.n_flights} flights`;
  }
  if (c.reachable) return `${where}: flown by ${c.n_ghost_flights} ghosts, logs from ${c.n_flights} flight(s) — uncharted`;
  return `${where}: no fleet rocket flies here`;
}
