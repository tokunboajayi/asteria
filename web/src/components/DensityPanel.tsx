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
  const altitude = (id: number) => objects.find((o) => o.norad_id === id)?.storm?.base_mean_altitude_km ?? null;
  const mine = d.objects.find((o) => o.norad_id === selected) ?? null;
  const measured = (id: number) => {
    const s = objects.find((o) => o.norad_id === id)?.storm;
    return s && s.in_track_km.length > 0 ? s.in_track_km[s.in_track_km.length - 1] : null;
  };
  /** Main-phase interval: measured from decay and NRLMSIS over the same interval. */
  const mainPhase = (id: number) => {
    const b = d.decay.find((o) => o.norad_id === id)?.bins[0];
    return (
      <>
        <td>
          {b?.measured_ratio != null ? `${fmtNum(b.measured_ratio, 2)} ± ${fmtNum(b.measured_err ?? 0, 2)}` : "—"}
        </td>
        <td>{b?.model_ratio != null ? fmtNum(b.model_ratio, 2) : "—"}</td>
      </>
    );
  };
  const yTicks = [1, ...[2, 3, 4, 5, 6, 8, 10].filter((v) => v < yMax)];

  return (
    <section className={panel.panel} aria-labelledby="density-title">
      <div className={panel.head}>
        <h2 id="density-title" className="label">
          Thermosphere density · storm ÷ quiet
        </h2>
        <span className={panel.tagGo}>{d.model ? "Measured · model" : "Measured"}</span>
      </div>
      <p className={panel.lead}>
        How much the storm raised air density along each satellite&apos;s real orbit, measured from the
        satellite&apos;s own orbit decay.
        {d.model
          ? ` The curves are ${d.model} driven by NASA OMNI indices (storm ÷ the same orbit with quiet geomagnetic activity), set beside the measurement over the same intervals.`
          : " No density model is configured, so only measurements are shown."}
      </p>
      {d.model && d.objects.length > 0 && (
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
      )}
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
      <h3 className="label">Measured from orbit decay{d.model ? " · vs model" : ""}</h3>
      {(() => {
        const dec = d.decay.find((o) => o.norad_id === selected);
        return dec ? <DecayChart d={dec} /> : null;
      })()}
      <table className={styles.table} aria-label="Main-phase density ratio, measured and modelled, and measured gap, per satellite">
        <thead>
          <tr>
            <th scope="col">Object</th>
            <th scope="col">Alt km</th>
            <th scope="col">Main phase measured ×</th>
            <th scope="col">Model ×</th>
            <th scope="col">Last gap km (measured)</th>
          </tr>
        </thead>
        <tbody>
          {[...d.decay]
            .map((o) => ({ o, alt: altitude(o.norad_id) }))
            .sort((a, b) => (a.alt ?? 0) - (b.alt ?? 0))
            .map(({ o, alt }) => {
              const g = measured(o.norad_id);
              return (
                <tr key={o.norad_id} className={o.norad_id === selected ? styles.selected : undefined}>
                  <th scope="row">{o.name}</th>
                  <td>{alt === null ? "—" : fmtNum(alt, 0)}</td>
                  {mainPhase(o.norad_id)}
                  <td>{g === null ? "—" : fmtSigned(g, 1)}</td>
                </tr>
              );
            })}
        </tbody>
      </table>
      <details className={panel.note}>
        <summary className="label">How this is computed</summary>
        {d.model && (
          <>
            <p>{d.method}</p>
            <p>
              Model: {d.model}. Licence: {d.model_licence}. Quiet-window mean daily Ap: {fmtNum(d.quiet_ap, 1)}.
            </p>
          </>
        )}
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
