"use client";

import type { ObjectDecay } from "@/lib/api";
import { linePath, scale } from "@/lib/chart";
import { fmtNum } from "@/lib/format";

import analysis from "./Analysis.module.css";
import styles from "./DensityPanel.module.css";
import panel from "./Panels.module.css";

const W = 640;
const H = 200;
const M = { left: 40, right: 10, top: 10, bottom: 26 };

/** One satellite: density ÷ quiet measured from its orbit decay (points ± 1σ) vs NRLMSIS (line). */
export function DecayChart({ d }: { d: ObjectDecay }) {
  if (d.status !== "measured") {
    return (
      <p className={panel.note} data-testid="decay-unmeasurable">
        {d.name}: not measurable from orbit decay. {d.reason}
      </p>
    );
  }
  const mid = (b: { start: string; end: string }) => (Date.parse(b.start) + Date.parse(b.end)) / 2;
  const ys = d.bins.flatMap((b) => [
    b.model_ratio ?? 1,
    (b.measured_ratio ?? 1) + (b.measured_err ?? 0),
  ]);
  const yMax = Math.max(1.5, ...ys);
  const yMin = Math.min(0.5, ...d.bins.map((b) => (b.measured_ratio ?? 1) - (b.measured_err ?? 0)));
  const x = scale({ min: Date.parse(d.bins[0].start), max: Date.parse(d.bins[d.bins.length - 1].end) }, M.left, W - M.right);
  const y = scale({ min: yMin, max: yMax }, H - M.bottom, M.top);
  const modelBins = d.bins.filter((b) => b.model_ratio !== null);
  const ticks = [1, 2, 3, 4, 5, 6, 8].filter((v) => v <= yMax && v >= yMin);
  const pk = d.peak;

  return (
    <div data-testid="decay-chart">
      <div className={styles.plot}>
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${d.name}: measured and modelled density ratio per day`}>
          {ticks.map((v) => (
            <text key={v} x={M.left - 5} y={y(v) + 4} textAnchor="end" className={analysis.tick}>
              {v}×
            </text>
          ))}
          <line x1={M.left} x2={W - M.right} y1={y(1)} y2={y(1)} className={analysis.unity} />
          <path
            d={linePath(modelBins.map(mid), modelBins.map((b) => b.model_ratio), x, y)}
            className={styles.model}
          />
          {d.bins.map((b) =>
            b.measured_ratio === null || b.measured_err === null ? null : (
              <g key={b.start}>
                <line
                  x1={x(mid(b))}
                  x2={x(mid(b))}
                  y1={y(b.measured_ratio - b.measured_err)}
                  y2={y(b.measured_ratio + b.measured_err)}
                  className={styles.errBar}
                />
                <circle cx={x(mid(b))} cy={y(b.measured_ratio)} r={4} className={styles.measured}>
                  <title>
                    {b.start.slice(0, 10)}: measured {fmtNum(b.measured_ratio, 2)} ± {fmtNum(b.measured_err, 2)}, model{" "}
                    {fmtNum(b.model_ratio, 2)}
                  </title>
                </circle>
              </g>
            ),
          )}
          <text x={(M.left + W - M.right) / 2} y={H - 4} textAnchor="middle" className={analysis.axisTitle}>
            ● measured from orbit decay (±1σ) · — NRLMSIS 2.1, same intervals
          </text>
        </svg>
      </div>
      {pk && pk.measured_ratio !== null && pk.model_ratio !== null && (
        <p className={panel.note} data-testid="decay-peak">
          Peak day {pk.start.slice(0, 10)}: measured {fmtNum(pk.measured_ratio, 2)} ± {fmtNum(pk.measured_err ?? 0, 2)}×
          quiet, model {fmtNum(pk.model_ratio, 2)}× (model ÷ measured {fmtNum(pk.model_ratio / pk.measured_ratio, 2)}).
          Quiet decay {fmtNum(d.quiet_decay_m_per_day ?? 0, 1)} m/day.
        </p>
      )}
    </div>
  );
}
