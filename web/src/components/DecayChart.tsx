"use client";

import type { ObjectDecay } from "@/lib/api";
import { fmtNum } from "@/lib/format";

import styles from "./DensityPanel.module.css";
import panel from "./Panels.module.css";

const LABEL = ["Main phase", "Recovery"];

const day = (iso: string) => iso.slice(5, 16).replace("T", " ");

/** One satellite: storm ÷ quiet density measured from its own orbit decay, beside NRLMSIS. */
export function DecayChart({ d }: { d: ObjectDecay }) {
  if (d.status !== "measured") {
    return (
      <p className={panel.note} data-testid="decay-unmeasurable">
        {d.name}: not measurable from orbit decay. {d.reason}
      </p>
    );
  }
  return (
    <div data-testid="decay-chart">
      <table className={styles.table} aria-label={`${d.name}: measured and modelled density ratio`}>
        <thead>
          <tr>
            <th scope="col">Interval (UTC)</th>
            <th scope="col">Measured ×</th>
            <th scope="col">Model ×</th>
            <th scope="col">Model ÷ measured</th>
          </tr>
        </thead>
        <tbody>
          {d.bins.map((b, i) => (
            <tr key={b.start}>
              <th scope="row">
                {LABEL[i] ?? "Interval"} · {day(b.start)} → {day(b.end)}
              </th>
              <td>
                {b.measured_ratio !== null
                  ? `${fmtNum(b.measured_ratio, 2)} ± ${fmtNum(b.measured_err ?? 0, 2)}`
                  : b.status === "below_noise"
                    ? "below noise"
                    : (b.note ?? "no fit")}
              </td>
              <td>{b.model_ratio !== null ? fmtNum(b.model_ratio, 2) : "—"}</td>
              <td>
                {b.measured_ratio !== null && b.model_ratio !== null
                  ? fmtNum(b.model_ratio / b.measured_ratio, 2)
                  : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className={panel.note}>
        Quiet reference: {fmtNum(d.quiet_decay_m_per_day ?? 0, 1)} m/day decay ({fmtNum(d.quiet_snr ?? 0, 0)}σ),{" "}
        {d.quiet_start?.slice(0, 10)} → {d.quiet_end?.slice(0, 10)}. Below 1 in the last column, the model
        under-predicts.
      </p>
    </div>
  );
}
