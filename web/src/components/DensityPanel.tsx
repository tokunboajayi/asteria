"use client";

import type { DensityReport, OrbitObjectSummary } from "@/lib/api";
import { linePath, scale } from "@/lib/chart";
import { fmtNum, fmtSigned } from "@/lib/format";
import type { Loadable } from "@/lib/useApi";

import analysis from "./Analysis.module.css";
import { DecayChart } from "./DecayChart";
import styles from "./DensityPanel.module.css";
import { PanelStatus } from "./PanelStatus";
import panel from "./Panels.module.css";

interface Props {
  density: Loadable<DensityReport>;
  objects: OrbitObjectSummary[];
  selected: number | null;
}

// SVG units. The plot is capped at W px wide (see .plot), so text stays at its stated size.
const W = 640;
const H = 220;
const M = { left: 40, right: 10, top: 10, bottom: 26 };

/**
 * NRLMSIS 2.1 density at each satellite's real positions, divided by the same model with
 * the quiet window's geomagnetic activity. Shown beside the measured in-track gap.
 */
export function DensityPanel({ density, objects, selected }: Props) {
  if (density.state !== "ready") return <PanelStatus title="Modelled density" state={density} />;
  const d = density.data;
  const all = d.objects.flatMap((o) => o.ratio);
  const yMax = Math.max(1.5, ...all);
  const t0 = Date.parse(d.objects[0]?.times[0] ?? "");
  const t1 = Math.max(...d.objects.map((o) => Date.parse(o.times[o.times.length - 1] ?? "")));
  const x = scale({ min: t0, max: t1 }, M.left, W - M.right);
  const y = scale({ min: 1, max: yMax }, H - M.bottom, M.top);
  const mine = d.objects.find((o) => o.norad_id === selected) ?? null;
  const measured = (id: number) => {
    const s = objects.find((o) => o.norad_id === id)?.storm;
    return s && s.in_track_km.length > 0 ? s.in_track_km[s.in_track_km.length - 1] : null;
  };
  const decayPeak = (id: number) => {
    const p = d.decay.find((o) => o.norad_id === id)?.peak;
    return p && p.measured_ratio !== null
      ? `${fmtNum(p.measured_ratio, 2)} ± ${fmtNum(p.measured_err ?? 0, 2)}×`
      : "—";
  };
  const yTicks = [1, ...[2, 3, 4, 5, 6, 8, 10].filter((v) => v < yMax)];

  return (
    <section className={panel.panel} aria-labelledby="density-title">
      <div className={panel.head}>
        <h2 id="density-title" className="label">
          Thermosphere density · storm ÷ quiet
        </h2>
        <span className={panel.tagNeutral}>Model · measured</span>
      </div>
      <p className={panel.lead}>
        How much the storm&apos;s geomagnetic heating raised air density along each satellite&apos;s real orbit,
        according to NRLMSIS 2.1 driven by NASA OMNI indices. A model, not a measurement: the measured in-track
        gap is beside it.
      </p>
      <div className={styles.plot} data-testid="density-plot">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Modelled density ratio over time, per satellite">
          {yTicks.map((v) => (
            <text key={v} x={M.left - 5} y={y(v) + 4} textAnchor="end" className={analysis.tick}>
              {v}×
            </text>
          ))}
          <line x1={M.left} x2={W - M.right} y1={y(1)} y2={y(1)} className={analysis.unity} />
          {d.objects.map((o) => (
            <path
              key={o.norad_id}
              d={linePath(
                o.times.map((t) => Date.parse(t)),
                o.ratio,
                x,
                y,
              )}
              className={o.norad_id === selected ? styles.mine : styles.other}
            >
              <title>
                {o.name}: peak {fmtNum(o.peak_ratio, 2)}× at {o.peak_time}
              </title>
            </path>
          ))}
          <text x={(M.left + W - M.right) / 2} y={H - 4} textAnchor="middle" className={analysis.axisTitle}>
            {d.objects[0]?.times[0]?.slice(0, 10)} → {new Date(t1).toISOString().slice(0, 10)}
          </text>
        </svg>
      </div>
      {mine && (
        <dl className={panel.kv} data-testid="density-mine">
          <dt>{mine.name} · peak (model)</dt>
          <dd>
            {fmtNum(mine.peak_ratio, 2)}× at {mine.peak_time}
          </dd>
          <dt>Mean altitude</dt>
          <dd>{fmtNum(mine.mean_altitude_km, 0)} km</dd>
          <dt>Last in-track gap (measured)</dt>
          <dd>{measured(mine.norad_id) === null ? "—" : `${fmtSigned(measured(mine.norad_id) ?? 0, 1)} km`}</dd>
        </dl>
      )}
      <h3 className="label">Measured from orbit decay · vs model</h3>
      {(() => {
        const dec = d.decay.find((o) => o.norad_id === selected);
        return dec ? <DecayChart d={dec} /> : null;
      })()}
      <table className={styles.table} aria-label="Peak modelled density ratio and measured gap, per satellite">
        <thead>
          <tr>
            <th scope="col">Object</th>
            <th scope="col">Alt km</th>
            <th scope="col">Peak (model)</th>
            <th scope="col">Peak day (decay)</th>
            <th scope="col">Last gap km (measured)</th>
          </tr>
        </thead>
        <tbody>
          {[...d.objects]
            .sort((a, b) => a.mean_altitude_km - b.mean_altitude_km)
            .map((o) => {
              const g = measured(o.norad_id);
              return (
                <tr key={o.norad_id} className={o.norad_id === selected ? styles.selected : undefined}>
                  <th scope="row">{o.name}</th>
                  <td>{fmtNum(o.mean_altitude_km, 0)}</td>
                  <td>{fmtNum(o.peak_ratio, 2)}×</td>
                  <td>{decayPeak(o.norad_id)}</td>
                  <td>{g === null ? "—" : fmtSigned(g, 1)}</td>
                </tr>
              );
            })}
        </tbody>
      </table>
      <details className={panel.note}>
        <summary className="label">How this is computed</summary>
        <p>{d.method}</p>
        <p>
          Model: {d.model}. Quiet-window mean daily Ap: {fmtNum(d.quiet_ap, 1)}.
        </p>
        <p>Orbit decay: {d.decay_method}</p>
        <ul>
          {[...d.caveats, ...d.decay_caveats].map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      </details>
    </section>
  );
}
