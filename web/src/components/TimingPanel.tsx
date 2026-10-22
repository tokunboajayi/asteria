"use client";

import type { FlightDetail, TimedEvent } from "@/lib/api";
import { fmtM, fmtNum, fmtSigned } from "@/lib/format";

import styles from "./Analysis.module.css";
import panels from "./Panels.module.css";

interface Props {
  detail: FlightDetail;
  onCursor: (t: number) => void;
}

/**
 * Event timing detective: what really happened, found in the log by code, beside
 * what the ghost predicted. Blank cells are measurements the data cannot support;
 * each carries its reason as a numbered note.
 */
export function TimingPanel({ detail, onCursor }: Props) {
  const { events, descent, accelerometer } = detail.timing;
  const notes = events.filter((e) => e.note);
  const noteNo = (e: TimedEvent) => notes.indexOf(e) + 1;
  const detected = events.filter((e) => e.status === "detected").length;
  return (
    <section className={panels.panel} aria-labelledby="timing-title">
      <div className={panels.head}>
        <h2 id="timing-title" className="label">
          Event timing · real vs ghost
        </h2>
        <span className={panels.tagNeutral} data-testid="timing-count">
          {detected}/{events.length} found
        </span>
      </div>
      <ul className={styles.events} aria-label="Event timing">
        {events.map((e) => (
          <li key={e.key} className={styles.event}>
            <div className={styles.eventHead}>
              <button
                type="button"
                className={styles.jump}
                onClick={() => onCursor(e.real_t ?? e.ghost_t)}
                title={`${e.method}. Click to move the cursor here.`}
              >
                {e.name}
                {e.note && <sup className={styles.noteRef}>{noteNo(e)}</sup>}
              </button>
              <span className={styles.delta}>
                {e.delta_t_s === null ? "not measured" : `Δ ${fmtSigned(e.delta_t_s, 2)} s`}
                {e.delta_altitude_m !== null && ` · ${fmtSigned(e.delta_altitude_m, 0)} m`}
              </span>
            </div>
            <div className={styles.eventValues}>
              <span className={styles.ghost}>
                ghost T+{fmtNum(e.ghost_t, 1)} s · {fmtM(e.ghost_altitude_m)} m
              </span>
              <span className={styles.real}>
                {e.real_t === null
                  ? "real —"
                  : `real T+${fmtNum(e.real_t, 1)} s${e.real_altitude_m === null ? "" : ` · ${fmtM(e.real_altitude_m)} m`}`}
              </span>
            </div>
          </li>
        ))}
      </ul>

      {descent.length > 0 && (
        <ul className={styles.events} aria-label="Descent rates">
          {descent.map((d) => (
            <li key={d.phase} className={styles.event}>
              <div className={styles.eventHead}>
                <span className={styles.phase}>{d.phase}</span>
                <span className={styles.delta}>
                  {d.ghost_mps === null || d.real_mps === null ? "" : `real ${fmtNum(d.real_mps / d.ghost_mps, 2)}× ghost`}
                </span>
              </div>
              <div className={styles.eventValues}>
                <span className={styles.ghost}>
                  {d.ghost_mps === null ? "ghost —" : `ghost ${fmtNum(-d.ghost_mps, 1)} m/s down`}
                </span>
                <span className={styles.real}>
                  {d.real_mps === null ? "real —" : `real ${fmtNum(-d.real_mps, 1)} m/s down`}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}

      {notes.length > 0 && (
        <ol className={styles.notes}>
          {notes.map((e) => (
            <li key={e.key}>{e.note}</li>
          ))}
        </ol>
      )}
      <p className={panels.note}>
        Every event is measured the same way on both flights, by code, on the liftoff-aligned clock. Blank
        means the data cannot support a number, never a guess.
        {accelerometer && <> Accelerometer: {accelerometer}</>}
      </p>
    </section>
  );
}
