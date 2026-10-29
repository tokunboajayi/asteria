"use client";

import dynamic from "next/dynamic";
import { useState } from "react";

import type { GapSeries, ObjectEphemeris } from "@/lib/api";
import { fmtNum, fmtSigned } from "@/lib/format";

import controls from "./Controls.module.css";
import type { CameraMode } from "./OrbitGlobe";
import styles from "./GlobeView.module.css";

const OrbitGlobe = dynamic(() => import("./OrbitGlobe").then((m) => m.OrbitGlobe), {
  ssr: false,
  loading: () => <div className={styles.placeholder}>Loading 3D orbit view…</div>,
});

interface Props {
  name: string;
  noradId: number;
  series: GapSeries;
  ephemeris: ObjectEphemeris;
  epochIndex: number;
}

const CAMERAS: [CameraMode, string][] = [
  ["overview", "Overview"],
  ["satellite", "Follow"],
  ["gap", "Gap"],
];
const SCALES = [1, 10, 50];

export function OrbitGlobeView({ name, noradId, series, ephemeris, epochIndex }: Props) {
  const [errorScale, setErrorScale] = useState(10);
  const [cameraMode, setCameraMode] = useState<CameraMode>("overview");
  const last = series.epochs.length - 1;
  const k = Math.min(Math.max(0, epochIndex), last);

  return (
    <section className={styles.view} aria-label="3D orbit view: ghost and tracked">
      <div className={styles.globe} data-testid="orbit-globe">
        <OrbitGlobe
          name={name}
          series={series}
          ephemeris={ephemeris}
          epochIndex={k}
          errorScale={errorScale}
          cameraMode={cameraMode}
        />
      </div>

      <div className={styles.caption}>
        <span className="label">
          {name} · NORAD {noradId} · {fmtNum(series.base_mean_altitude_km, 0)} km · period{" "}
          {fmtNum(ephemeris.period_min, 1)} min
        </span>
      </div>

      {k >= 0 && (
        <div className={styles.gapBadge} data-testid="orbit-gap-badge">
          <span className="label">Gap · tracked − ghost · {series.epochs[k]}</span>
          <strong>{fmtSigned(series.in_track_km[k], 1)} km in-track</strong>
          <span className={styles.gapPct}>
            radial {fmtSigned(series.radial_km[k], 2)} km · cross {fmtSigned(series.cross_track_km[k], 2)} km
          </span>
        </div>
      )}

      <div className={styles.orbitTools}>
        <div role="group" aria-label="Camera" className={controls.group}>
          {CAMERAS.map(([mode, label]) => (
            <button
              key={mode}
              type="button"
              aria-pressed={cameraMode === mode}
              className={cameraMode === mode ? controls.buttonOn : controls.button}
              onClick={() => setCameraMode(mode)}
            >
              {label}
            </button>
          ))}
        </div>
        <div role="group" aria-label="Gap drawn at" className={controls.group}>
          <span className={controls.groupLabel}>Gap drawn</span>
          {SCALES.map((s) => (
            <button
              key={s}
              type="button"
              aria-pressed={errorScale === s}
              className={errorScale === s ? controls.buttonOn : controls.button}
              onClick={() => setErrorScale(s)}
            >
              {s}×
            </button>
          ))}
        </div>
      </div>

      <ul className={styles.legend} aria-label="Legend">
        <li>
          <span className={styles.swatchGhost} aria-hidden="true" /> Ghost · SGP4 from the last pre-storm element set
        </li>
        <li>
          <span className={styles.swatchReal} aria-hidden="true" /> Tracked · latest Space-Track element set
        </li>
        <li>
          <span className={styles.swatchGap} aria-hidden="true" /> Gap at the chosen epoch
        </li>
      </ul>
    </section>
  );
}
