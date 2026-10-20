"use client";

import type { NextBest } from "@/lib/api";
import { fmtNum } from "@/lib/format";
import type { Loadable } from "@/lib/useApi";

import { PanelStatus } from "./PanelStatus";
import styles from "./Panels.module.css";

/** The envelope where one more flight would remove the most uncertainty. */
export function NextBestPanel({ nextBest }: { nextBest: Loadable<NextBest> }) {
  if (nextBest.state !== "ready") return <PanelStatus title="Next best flight" state={nextBest} />;
  const n = nextBest.data;
  return (
    <section className={styles.panel} aria-labelledby="nextbest-title">
      <div className={styles.head}>
        <h2 id="nextbest-title" className="label">
          Next best flight · test plan
        </h2>
        <span className={styles.tagNeutral}>Most to learn</span>
      </div>
      <div className={styles.grid2}>
        <div className={styles.tile}>
          <div>Target Mach</div>
          <div data-testid="nextbest-mach">
            {fmtNum(n.target.mach[0], 1)}–{fmtNum(n.target.mach[1], 1)}
          </div>
        </div>
        <div className={styles.tile}>
          <div>Target altitude AGL</div>
          <div>
            {fmtNum(n.target.alt_m[0], 0)}–{fmtNum(n.target.alt_m[1], 0)} m
          </div>
        </div>
        <div className={styles.tile}>
          <div>Closest flown vehicle</div>
          <div>{n.nearest_flight.name}</div>
        </div>
        <div className={styles.tile}>
          <div>Its ghost peak Mach</div>
          <div>{fmtNum(n.nearest_flight.max_mach_ghost, 2)}</div>
        </div>
      </div>
      <p className={styles.note}>{n.rationale}</p>
      {n.ghost_flights.length > 0 && (
        <p className={styles.note}>
          Ghosts that already fly through it: <span className="mono">{n.ghost_flights.join(", ")}</span>.
        </p>
      )}
      <p className={styles.note}>
        <strong>Limit:</strong> {n.limitation}
      </p>
    </section>
  );
}
