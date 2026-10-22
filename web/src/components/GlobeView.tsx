"use client";

import dynamic from "next/dynamic";

import type { FlightDetail } from "@/lib/api";
import { fmtM, fmtMet, fmtNum, fmtPct, fmtSigned } from "@/lib/format";
import { stateAt, type Mode } from "@/lib/flightView";
import { calloutAt, phaseAt } from "@/lib/replay";
import { useReducedMotion } from "@/lib/useReducedMotion";
import { buildRuler } from "@/lib/ruler";

import styles from "./GlobeView.module.css";

// Cesium needs the browser (WebGL, window), so it is loaded on the client only.
const Globe = dynamic(() => import("./Globe").then((m) => m.Globe), {
  ssr: false,
  loading: () => <div className={styles.placeholder}>Loading 3D view…</div>,
});

interface Props {
  detail: FlightDetail;
  mode: Mode;
  cursor: number;
  replay: boolean;
}

export function GlobeView({ detail, mode, cursor, replay }: Props) {
  const reducedMotion = useReducedMotion();
  const hasTrack = detail.real.gnss !== null;
  const ruler = buildRuler(detail, mode, fmtM);
  const modelName = ruler.modelName.toLowerCase();
  return (
    <section className={styles.view} aria-label="Trajectory view">
      <div className={styles.globe} data-testid="globe">
        <Globe detail={detail} mode={mode} cursor={cursor} follow={replay && !reducedMotion} />
      </div>
      <div className={styles.caption}>
        <span className="label">Trajectory · 3D globe</span>
      </div>
      {replay && <ReplayHud detail={detail} mode={mode} cursor={cursor} />}
      <div className={styles.gapBadge} data-testid="globe-gap">
        <span className="label">Apogee gap · real − {modelName}</span>
        <strong>{fmtSigned(ruler.gap, 0)} m</strong>
        <span className={styles.gapPct}>
          {modelName} error {fmtPct(((ruler.model.agl - ruler.real.agl) / ruler.real.agl) * 100)}
        </span>
      </div>
      <ul className={styles.legend} aria-label="Legend">
        <li>
          <span className={styles.swatchGhost} aria-hidden="true" /> Ghost · physics only
        </li>
        {mode === "corrected" && detail.corrected && (
          <li>
            <span className={styles.swatchCorrected} aria-hidden="true" /> Corrected · held out
          </li>
        )}
        <li>
          <span className={hasTrack ? styles.swatchReal : styles.swatchDot} aria-hidden="true" />{" "}
          {hasTrack ? "Real · GNSS position + logged altitude" : "Real · logged altitude, on the pad ruler"}
        </li>
        <li>
          <span className={styles.swatchGap} aria-hidden="true" /> Apogee gap · real − model
        </li>
      </ul>
    </section>
  );
}

const TRANSONIC = [0.8, 1.2] as const;

const PHASE_LABEL = { pad: "On the pad", boost: "Boost", coast: "Coast", descent: "Descent" } as const;

/** Mission-control readout during a replay: clock, phase, ghost vs real, latest event. */
function ReplayHud({ detail, mode, cursor }: { detail: FlightDetail; mode: Mode; cursor: number }) {
  const rows = stateAt(detail, cursor, mode);
  const alt = rows.find((r) => r.key === "alt");
  const vz = rows.find((r) => r.key === "vz");
  const mach = rows.find((r) => r.key === "mach")?.ghost ?? null;
  // Same band the engine uses: barometric altitude (and speed derived from it) can misread here.
  const transonic = mach !== null && mach >= TRANSONIC[0] && mach <= TRANSONIC[1];
  const callout = calloutAt(detail, cursor);
  const value = (v: number | null | undefined, digits: number) => (v === null || v === undefined ? "—" : fmtNum(v, digits));
  return (
    <div className={styles.hud} data-testid="replay-hud" aria-live="polite">
      <div className={styles.hudTop}>
        <span className={styles.hudClock}>{fmtMet(cursor)}</span>
        <span className={styles.hudPhase}>{PHASE_LABEL[phaseAt(detail, cursor)]}</span>
      </div>
      <dl className={styles.hudGrid}>
        <dt>ALT m</dt>
        <dd className={styles.hudGhost}>{value(alt?.ghost, 0)}</dd>
        <dd className={styles.hudReal}>{value(alt?.real, 0)}</dd>
        <dt>VZ m/s</dt>
        <dd className={styles.hudGhost}>{value(vz?.ghost, 1)}</dd>
        <dd className={styles.hudReal}>{value(vz?.real, 1)}</dd>
      </dl>
      {transonic && (
        <p className={styles.hudWarn}>Near Mach {fmtNum(mach, 2)}: the real altimeter can misread here.</p>
      )}
      {callout && (
        <div key={callout.key} className={callout.source === "real" ? styles.calloutReal : styles.callout}>
          <strong>{callout.title}</strong>
          <span>{callout.detail}</span>
        </div>
      )}
    </div>
  );
}
