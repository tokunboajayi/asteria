"use client";

import type { AccelDensity } from "@/lib/api";
import { linePath, scale } from "@/lib/chart";
import { fmtNum } from "@/lib/format";

import analysis from "./Analysis.module.css";
import styles from "./DensityPanel.module.css";
import panel from "./Panels.module.css";

const W = 640;
const H = 200;
const M = { left: 48, right: 10, top: 10, bottom: 26 };
const LABEL = ["Main phase", "Recovery"];

/** GRACE-FO 1 accelerometer: the independent check on the decay method and the model. */
export function AccelCheck({ a }: { a: AccelDensity }) {
  const ms = a.times.map((t) => Date.parse(t));
  const vals = [...(a.model_kg_m3 ?? []), ...a.measured_kg_m3.filter((v): v is number => v !== null)];
  const x = scale({ min: ms[0], max: ms[ms.length - 1] }, M.left, W - M.right);
  const y = scale({ min: 0, max: Math.max(...vals) * 1.05 }, H - M.bottom, M.top);
  const ticks = [1, 2, 3, 4, 5, 6].map((v) => v * 1e-12).filter((v) => v <= Math.max(...vals) * 1.05);

  return (
    <section className={panel.panel} aria-labelledby="accel-title" data-testid="accel-check">
      <div className={panel.head}>
        <h2 id="accel-title" className="label">
          Independent check · GRACE-FO 1 accelerometer
        </h2>
        <span className={panel.tagGo}>Measured</span>
      </div>
      <p className={panel.lead}>
        GRACE-FO&apos;s accelerometer measures drag directly. Same intervals as the orbit-decay method: if the two
        measurements agree, the decay method can be trusted for the satellites that carry no accelerometer.
      </p>
      <table className={styles.table} aria-label="Accelerometer, orbit decay and model, same intervals">
        <thead>
          <tr>
            <th scope="col">Interval</th>
            <th scope="col">Accelerometer ×</th>
            <th scope="col">Orbit decay ×</th>
            <th scope="col">Model ×</th>
          </tr>
        </thead>
        <tbody>
          {a.checks.map((c, i) => (
            <tr key={c.start}>
              <th scope="row">{LABEL[i] ?? "Interval"}</th>
              <td>{c.accel_ratio !== null ? fmtNum(c.accel_ratio, 2) : "—"}</td>
              <td>
                {c.decay_ratio !== null ? `${fmtNum(c.decay_ratio, 2)} ± ${fmtNum(c.decay_err ?? 0, 2)}` : "—"}
              </td>
              <td>{c.model_ratio !== null ? fmtNum(c.model_ratio, 2) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className={styles.plot}>
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Absolute density, accelerometer and model, hourly">
          {ticks.map((v) => (
            <text key={v} x={M.left - 5} y={y(v) + 4} textAnchor="end" className={analysis.tick}>
              {fmtNum(v * 1e12, 0)}
            </text>
          ))}
          {a.model_kg_m3 && <path d={linePath(ms, a.model_kg_m3, x, y)} className={styles.model} />}
          <path d={linePath(ms, a.measured_kg_m3, x, y)} className={styles.measuredLine} />
          <text x={(M.left + W - M.right) / 2} y={H - 4} textAnchor="middle" className={analysis.axisTitle}>
            ×10⁻¹² kg/m³ · white: accelerometer{a.model_kg_m3 ? " · blue dashed: model, same orbit" : ""}
          </text>
        </svg>
      </div>
      <p className={panel.note}>
        {a.median_model_over_measured !== null &&
          `Typical hour: the model is ${fmtNum(a.median_model_over_measured, 2)}× the measured density (median); ratios cancel that bias. `}
        {a.source}.
      </p>
    </section>
  );
}
