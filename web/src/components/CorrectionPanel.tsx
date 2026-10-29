"use client";

import type { CorrectionReport } from "@/lib/api";
import { fmtNum, fmtPct } from "@/lib/format";
import type { Loadable } from "@/lib/useApi";

import { PanelStatus } from "./PanelStatus";
import styles from "./Panels.module.css";

interface Props {
  report: Loadable<CorrectionReport>;
  flightId: string;
}

/** The held-out result, stated plainly whichever way it went. */
export function CorrectionPanel({ report, flightId }: Props) {
  if (report.state !== "ready") return <PanelStatus title="Fleet correction" state={report} />;
  const r = report.data;
  const a = r.aggregate;
  const helped = a.median_abs_err_after_pct < a.median_abs_err_before_pct;
  const mine = r.per_flight.find((p) => p.id === flightId);
  const worst = Math.max(...r.per_flight.flatMap((p) => [Math.abs(p.err_before_pct), Math.abs(p.err_after_pct)]));
  return (
    <section className={styles.panel} aria-labelledby="correction-title">
      <div className={styles.head}>
        <h2 id="correction-title" className="label">
          Fleet correction · held out
        </h2>
        <span className={helped ? styles.tagGo : styles.tagCaution}>{helped ? "Helps" : "Does not help"}</span>
      </div>
      <p className={styles.lead} data-testid="correction-verdict">
        Median apogee error {fmtNum(a.median_abs_err_before_pct, 1)}% with physics alone,{" "}
        {fmtNum(a.median_abs_err_after_pct, 1)}% with the correction ({a.n_improved} flights closer,{" "}
        {a.n_worse} further).
      </p>
      <p className={styles.note}>
        {r.model}. Each flight is predicted from the other flights only ({r.evaluation}). Fixed before any
        result was seen; no other model was tried.
      </p>
      {mine && (
        <dl className={styles.kv}>
          <dt>This flight · own k</dt>
          <dd>{fmtNum(mine.k_own, 3)}</dd>
          <dt>Held-out k̂</dt>
          <dd>{fmtNum(mine.k_hat, 3)}</dd>
          <dt>Error before → after</dt>
          <dd>
            {fmtPct(mine.err_before_pct)} → {fmtPct(mine.err_after_pct)}
          </dd>
        </dl>
      )}
      <table className={styles.bars}>
        <caption className="visually-hidden">Apogee error per flight, physics alone and corrected</caption>
        <thead>
          <tr>
            <th scope="col">Flight</th>
            <th scope="col">Error · physics (blue) vs corrected (green)</th>
          </tr>
        </thead>
        <tbody>
          {r.per_flight.map((p) => (
            <tr key={p.id} className={p.id === flightId ? styles.selected : undefined}>
              <th scope="row" className="mono">
                {p.id}
              </th>
              <td>
                <Bar value={p.err_before_pct} max={worst} kind="ghost" />
                <Bar value={p.err_after_pct} max={worst} kind="corrected" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {r.band_coverage && (
        <p className={styles.note} data-testid="band-coverage">
          Fleet band check: {r.band_coverage.inside} of {r.band_coverage.flights} real apogees fell inside the band
          built from the other flights (expected {fmtNum(r.band_coverage.expected_inside, 1)}).
          {r.band_coverage.outside_ids.length > 0 && ` Outside: ${r.band_coverage.outside_ids.join(", ")}.`}
        </p>
      )}
    </section>
  );
}

function Bar({ value, max, kind }: { value: number; max: number; kind: "ghost" | "corrected" }) {
  const width = max > 0 ? (Math.abs(value) / max) * 50 : 0;
  const left = value < 0 ? 50 - width : 50;
  return (
    <div className={styles.barRow}>
      <div className={styles.barTrack}>
        <div className={styles.barZero} />
        <div
          className={kind === "ghost" ? styles.barGhost : styles.barCorrected}
          style={{ left: `${left}%`, width: `${width}%` }}
        />
      </div>
      <span className={styles.barValue}>{fmtPct(value)}</span>
    </div>
  );
}
