"use client";

import dynamic from "next/dynamic";

import type { FlightDetail } from "@/lib/api";
import { fmtM, fmtPct, fmtSigned } from "@/lib/format";
import type { Mode } from "@/lib/flightView";
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
}

export function GlobeView({ detail, mode, cursor }: Props) {
  const hasTrack = detail.real.gnss !== null;
  const ruler = buildRuler(detail, mode, fmtM);
  const modelName = ruler.modelName.toLowerCase();
  return (
    <section className={styles.view} aria-label="Trajectory view">
      <div className={styles.globe} data-testid="globe">
        <Globe detail={detail} mode={mode} cursor={cursor} />
      </div>
      <div className={styles.caption}>
        <span className="label">Trajectory · 3D globe</span>
      </div>
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
