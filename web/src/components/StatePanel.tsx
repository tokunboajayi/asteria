"use client";

import type { FlightDetail } from "@/lib/api";
import { stateAt, type Mode } from "@/lib/flightView";
import { fmtM, fmtNum, fmtPct, fmtSigned } from "@/lib/format";

import styles from "./StatePanel.module.css";

interface Props {
  detail: FlightDetail;
  mode: Mode;
  onMode: (m: Mode) => void;
  cursor: number;
}

export function StatePanel({ detail, mode, onMode, cursor }: Props) {
  const rows = stateAt(detail, cursor, mode);
  const s = detail.summary;
  const d = detail.diagnostics;
  const corrected = mode === "corrected" && detail.corrected !== null;
  const modelName = corrected ? "Corrected" : "Ghost";
  return (
    <div className={styles.panel}>
      <section className={styles.block}>
        <h2 className="label">Apogee AGL</h2>
        <dl className={styles.apogee}>
          <div>
            <dt>Real (log peak)</dt>
            <dd>
              <span data-testid="apogee-real">{fmtM(s.apogee.real_m)}</span> m
            </dd>
          </div>
          <div>
            <dt className={styles.ghostText}>Ghost</dt>
            <dd>
              <span data-testid="apogee-ghost">{fmtM(s.apogee.ghost_m)}</span> m
            </dd>
          </div>
          <div>
            <dt className={styles.gapText}>Ghost error</dt>
            <dd className={styles.gapText}>{fmtPct(s.apogee.ghost_error_pct)}</dd>
          </div>
          {s.correction && (
            <div>
              <dt className={styles.correctedText}>Corrected (held out)</dt>
              <dd>
                {fmtM(s.correction.corrected_apogee_m)} m · {fmtPct(s.correction.err_after_pct)}
              </dd>
            </div>
          )}
          <div>
            <dt>Team pre-flight</dt>
            <dd title={s.team_prediction?.quote}>
              {s.team_prediction ? `${fmtM(s.team_prediction.value_m)} m` : "not published"}
            </dd>
          </div>
          <div>
            <dt>Flight card</dt>
            <dd title={s.official_apogee?.quote}>
              {s.official_apogee ? `${fmtM(s.official_apogee.value_m)} m` : "not published"}
            </dd>
          </div>
        </dl>
      </section>

      <section className={styles.block}>
        <h2 className="label">Vehicle state at cursor</h2>
        <table className={styles.table} aria-label="Vehicle state">
          <thead>
            <tr>
              <th scope="col">Param</th>
              <th scope="col" className={corrected ? styles.correctedText : styles.ghostText}>
                {modelName}
              </th>
              <th scope="col">Real</th>
              <th scope="col" className={styles.gapText}>
                Δ
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key} title={r.realNote}>
                <th scope="row">
                  {r.label} <span className={styles.unit}>{r.unit}</span>
                </th>
                <td className={corrected ? styles.correctedText : styles.ghostText}>{fmtNum(r.ghost, r.digits)}</td>
                <td className={styles.realText}>{fmtNum(r.real, r.digits)}</td>
                <td className={r.delta === null ? styles.dim : styles.gapText}>{fmtSigned(r.delta, r.digits)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className={styles.footnote}>
          “—” means not measured or not modelled. Real vertical velocity is derived from logged altitude
          with one fixed filter for every flight.
        </p>
      </section>

      <section className={styles.block}>
        <h2 className="label">Model</h2>
        <div className={styles.row}>
          <span>Physics core</span>
          <span className={styles.correctedText}>RocketPy 6-DOF reconstruction</span>
        </div>
        <div className={styles.row}>
          <span>Learned correction</span>
          <span data-testid="correction-state" className={corrected ? styles.correctedText : styles.dim}>
            {corrected && s.correction ? `ON · drag × ${fmtNum(s.correction.k_hat, 3)} (held out)` : "OFF · pure physics"}
          </span>
        </div>
        <button
          type="button"
          className={styles.toggle}
          disabled={detail.corrected === null}
          onClick={() => onMode(corrected ? "physics" : "corrected")}
        >
          {corrected ? "Show pure physics" : "Apply learned correction"}
        </button>
      </section>

      <section className={styles.block}>
        <h2 className="label">Data quality</h2>
        <ul className={styles.chips}>
          <li className={d.importer_cross_check === "identical" ? styles.go : styles.neutral}>
            {d.importer_cross_check === "identical" ? "Loader = notebook importer" : "No importer to cross-check"}
          </li>
          <li className={d.coarse_log ? styles.caution : styles.go}>
            Log every {fmtNum(d.median_sample_interval_s, 3)} s{d.coarse_log ? " · coarse" : ""}
          </li>
          <li className={d.liftoff_offset_s === null ? styles.caution : styles.go}>
            {d.liftoff_offset_s === null
              ? "No liftoff found · clocks unaligned"
              : `Liftoff aligned ${fmtSigned(d.liftoff_offset_s, 2)} s`}
          </li>
          <li className={s.has_position ? styles.go : styles.neutral}>
            {s.has_position ? "GNSS track logged" : "Altitude only · no position"}
          </li>
          {d.rows_after_cutoff > 0 && (
            <li className={styles.caution}>{d.rows_after_cutoff} rows past declared cutoff</li>
          )}
        </ul>
      </section>
    </div>
  );
}
