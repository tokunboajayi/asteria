"use client";

import dynamic from "next/dynamic";

import type { FlightDetail } from "@/lib/api";
import type { Mode } from "@/lib/flightView";

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
  return (
    <section className={styles.view} aria-label="Trajectory view">
      <div className={styles.globe} data-testid="globe">
        <Globe detail={detail} mode={mode} cursor={cursor} />
      </div>
      <div className={styles.caption}>
        <span className="label">Trajectory · 3D globe</span>
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
          <span className={hasTrack ? styles.swatchReal : styles.swatchNone} aria-hidden="true" />{" "}
          {hasTrack ? "Real · GNSS position + logged altitude" : "Real · altitude only, no position logged"}
        </li>
      </ul>
    </section>
  );
}
