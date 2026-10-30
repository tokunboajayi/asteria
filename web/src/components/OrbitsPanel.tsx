"use client";

import { useState } from "react";

import type {
  DensityReport,
  GapMap,
  GapSeries,
  ObjectEphemeris,
  OrbitFleet,
  OrbitsStatus,
  SpaceWeatherSeries,
} from "@/lib/api";
import { clamp, extent, linePath, padded, scale, symmetric } from "@/lib/chart";
import { fmtNum, fmtSigned } from "@/lib/format";
import { useApi, type Loadable } from "@/lib/useApi";

import { GapMapPanel } from "./GapMapPanel";
import { AccelCheck } from "./AccelCheck";
import controls from "./Controls.module.css";
import { DensityPanel } from "./DensityPanel";
import { ExportDialog } from "./ExportDialog";
import { OrbitGlobeView } from "./OrbitGlobeView";
import styles from "./OrbitsPanel.module.css";
import panel from "./Panels.module.css";

/** Storm Ghost. Shows nothing but its status until verified orbit artifacts exist. */
export function OrbitsPanel({ status }: { status: Loadable<OrbitsStatus> }) {
  const available = status.state === "ready" && status.data.available;
  return (
    <div className={styles.wrap}>
      {!available && (
        <section className={panel.panel} aria-labelledby="orbits-title">
          <h2 id="orbits-title" className="label">
            Orbits · Storm Ghost
          </h2>
          {status.state === "loading" && <p className={panel.note}>Loading…</p>}
          {status.state === "error" && (
            <p className={panel.note} role="alert">
              Unavailable: {status.message}
            </p>
          )}
          {status.state === "ready" && (
            <p className={panel.lead} data-testid="orbits-gated">
              {status.data.reason}
            </p>
          )}
          <p className={panel.note}>
            Storm Ghost propagates each satellite&apos;s orbit with SGP4 from its last element set before a
            geomagnetic storm (the ghost) and compares it with the orbits tracking fitted afterwards, alongside
            NASA OMNI space-weather indices for the same hours.
          </p>
        </section>
      )}
      {available && <OrbitsData />}
    </div>
  );
}

function OrbitsData() {
  const fleet = useApi<OrbitFleet>("/api/orbits/fleet");
  const weather = useApi<SpaceWeatherSeries>("/api/orbits/spaceweather");
  const gap = useApi<GapMap>("/api/orbits/gapmap");
  const [chosen, setChosen] = useState<number | null>(null);
  // null = the latest tracked epoch, as before the scrubber is touched.
  const [k, setK] = useState<number | null>(null);
  const [showExport, setShowExport] = useState(false);

  const defaultId =
    fleet.state === "ready"
      ? (fleet.data.objects.filter((o) => o.storm !== null)[0]?.norad_id ?? null)
      : null;
  const id = chosen ?? defaultId;
  const eph = useApi<ObjectEphemeris>(id ? `/api/orbits/ephemeris/${id}` : null);
  const density = useApi<DensityReport>("/api/orbits/density");

  if (fleet.state !== "ready") {
    return <p className={panel.note}>{fleet.state === "error" ? fleet.message : "Loading orbits…"}</p>;
  }
  const f = fleet.data;
  const shown = f.objects.filter((o) => o.storm !== null);
  const obj = f.objects.find((o) => o.norad_id === id) ?? null;

  return (
    <div className={styles.grid}>
      {obj?.storm && eph.state === "ready" && eph.data.norad_id === obj.norad_id && (
        <OrbitGlobeView
          name={obj.name}
          noradId={obj.norad_id}
          series={obj.storm}
          ephemeris={eph.data}
          epochIndex={k ?? obj.storm.epochs.length - 1}
        />
      )}

      <section className={panel.panel} aria-labelledby="storm-title">
        <div className={controls.headRow}>
          <h2 id="storm-title" className="label">
            {f.storm.name}
          </h2>
          <button type="button" className={controls.button} onClick={() => setShowExport(true)}>
            CCSDS OEM · Open MCT
          </button>
        </div>

        <dl className={panel.kv}>
          <dt>Onset (ghost epochs end here)</dt>
          <dd>{f.storm.onset}</dd>
          <dt>Peak Kp · lowest Dst</dt>
          <dd>
            {fmtNum(f.storm.peak_kp, 1)} · {fmtNum(f.storm.min_dst_nt, 0)} nT
          </dd>
          <dt>Quiet baseline (Kp ≤ {fmtNum(f.storm.quiet_max_kp, 1)})</dt>
          <dd>{f.storm.quiet_start ? `${f.storm.quiet_start} → ${f.storm.quiet_end}` : "none found"}</dd>
          <dt>Followed for</dt>
          <dd>{fmtNum(f.storm.follow_days, 1)} days</dd>
        </dl>
        <label htmlFor="sat-picker" className="label">
          Satellite
        </label>
        <select
          id="sat-picker"
          className={styles.select}
          value={id ?? ""}
          onChange={(e) => {
            setChosen(Number(e.target.value));
            setK(null);
          }}
        >
          {shown.map((o) => (
            <option key={o.norad_id} value={o.norad_id}>
              {o.name} · {o.norad_id}
            </option>
          ))}
        </select>
        {f.objects
          .filter((o) => o.excluded_reason)
          .map((o) => (
            <p key={o.norad_id} className={panel.note}>
              {o.name}: {o.excluded_reason}
            </p>
          ))}
      </section>

      {obj?.storm && (
        <>
          <OrbitState key={obj.norad_id} series={obj.storm} k={k ?? obj.storm.epochs.length - 1} onKChange={setK} />
          <GapChart storm={obj.storm} quiet={obj.quiet} />
        </>
      )}

      <DensityPanel density={density} objects={f.objects} selected={id} />
      {density.state === "ready" && density.data.accelerometer && <AccelCheck a={density.data.accelerometer} />}

      {weather.state === "ready" && <WeatherChart weather={weather.data} onset={f.storm.onset} />}
      <GapMapPanel gap={gap} flightId={String(id ?? "")} noun="objects" />
      <p className={panel.note}>
        Element sets: {f.provenance.spacetrack_query.replace(/^https:\/\/www\.space-track\.org/, "space-track.org")}{" "}
        · downloaded {f.provenance.spacetrack_downloaded_at} · sgp4 {f.provenance.sgp4_version}. Raw Space-Track
        data stays on this machine (its user agreement forbids redistribution).
      </p>

      {showExport && obj && (
        <ExportDialog
          name={obj.name}
          oemPath={obj.storm ? `/api/export/oem/orbit/${obj.norad_id}` : null}
          oemNote={
            obj.storm
              ? "TEME states every 5 minutes from the storm onset, each from SGP4 on the latest Space-Track element set at or before it. Positions and velocities."
              : "No element set before the storm onset, so no ephemeris was built."
          }
          onClose={() => setShowExport(false)}
        />
      )}
    </div>
  );
}

function OrbitState({
  series,
  k,
  onKChange,
}: {
  series: GapSeries;
  k: number;
  onKChange: (k: number) => void;
}) {
  const last = series.epochs.length - 1;
  const index = clamp(k, 0, last);
  if (last < 0) {
    return <p className={panel.note}>No tracked element set after the ghost&apos;s epoch.</p>;
  }
  const rows: [string, string, number, number, number][] = [
    ["ALT", "km", series.ghost_alt_km[index], series.tracked_alt_km[index], 3],
    ["LAT", "°", series.ghost_lat[index], series.tracked_lat[index], 4],
    ["LON", "°", series.ghost_lon[index], series.tracked_lon[index], 4],
  ];
  return (
    <section className={panel.panel} aria-labelledby="orbit-state-title">
      <h2 id="orbit-state-title" className="label">
        At {series.epochs[index]} · {fmtNum(series.days[index], 2)} days after the ghost&apos;s epoch
      </h2>
      <label htmlFor="epoch-scrub" className="visually-hidden">
        Tracked element set
      </label>
      <input
        id="epoch-scrub"
        type="range"
        min={0}
        max={last}
        value={index}
        onChange={(e) => onKChange(Number(e.target.value))}
        className={styles.range}
      />
      <table className={styles.table} aria-label="Orbit state">
        <thead>
          <tr>
            <th scope="col">Param</th>
            <th scope="col">Ghost</th>
            <th scope="col">Tracked</th>
            <th scope="col">Δ</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, unit, g, t, d]) => (
            <tr key={label}>
              <th scope="row">
                {label} <span className={styles.unit}>{unit}</span>
              </th>
              <td>{fmtNum(g, d)}</td>
              <td>{fmtNum(t, d)}</td>
              <td>{fmtSigned(t - g, d)}</td>
            </tr>
          ))}
          <tr>
            <th scope="row">
              Radial <span className={styles.unit}>km</span>
            </th>
            <td colSpan={2}>tracked − ghost</td>
            <td>{fmtSigned(series.radial_km[k], 3)}</td>
          </tr>
          <tr>
            <th scope="row">
              In-track <span className={styles.unit}>km</span>
            </th>
            <td colSpan={2}>negative = behind the ghost</td>
            <td>{fmtSigned(series.in_track_km[k], 3)}</td>
          </tr>
          <tr>
            <th scope="row">
              Cross-track <span className={styles.unit}>km</span>
            </th>
            <td colSpan={2}>tracked − ghost</td>
            <td>{fmtSigned(series.cross_track_km[k], 3)}</td>
          </tr>
        </tbody>
      </table>
      {series.stopped_by_maneuver_at && (
        <p className={panel.note}>Maneuver at {series.stopped_by_maneuver_at}: the ghost is not compared past it.</p>
      )}
    </section>
  );
}

const W = 1000;
const H = 120;

function GapChart({ storm, quiet }: { storm: GapSeries; quiet: GapSeries | null }) {
  const lines = [{ days: storm.days, v: storm.in_track_km, cls: styles.storm }];
  if (quiet) lines.push({ days: quiet.days, v: quiet.in_track_km, cls: styles.quiet });
  const xMax = Math.max(1e-9, ...lines.flatMap((l) => l.days));
  const data = extent(lines.map((l) => l.v));
  const y = scale(symmetric(data ?? { min: -1, max: 1 }), H - 6, 6);
  const x = scale({ min: 0, max: xMax }, 0, W);
  return (
    <section className={panel.panel} aria-labelledby="gapchart-title">
      <h2 id="gapchart-title" className="label">
        In-track gap vs days since the ghost&apos;s epoch
      </h2>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        className={styles.chart}
        role="img"
        aria-label="In-track gap over time, storm window and quiet baseline"
      >
        <line x1={0} x2={W} y1={y(0)} y2={y(0)} className={styles.zero} vectorEffect="non-scaling-stroke" />
        {lines.map((l) => (
          <path key={l.cls} d={linePath(l.days, l.v, x, y)} className={l.cls} vectorEffect="non-scaling-stroke" />
        ))}
      </svg>
      <div className={panel.legendRow}>
        <span>
          <span className={`${panel.key} ${styles.keyStorm}`} aria-hidden="true" />
          storm window
        </span>
        {quiet && (
          <span>
            <span className={`${panel.key} ${styles.keyQuiet}`} aria-hidden="true" />
            quiet baseline
          </span>
        )}
        <span>
          range {data ? `${fmtNum(data.min, 1)} to ${fmtNum(data.max, 1)} km` : "—"}
        </span>
      </div>
    </section>
  );
}

function WeatherChart({ weather, onset }: { weather: SpaceWeatherSeries; onset: string }) {
  const t = weather.times.map((s) => Date.parse(s));
  const x = scale({ min: t[0], max: t[t.length - 1] }, 0, W);
  const kpY = scale({ min: 0, max: 9 }, H - 6, 6);
  const dstData = extent([weather.dst_nt]);
  const dstY = scale(padded(dstData ?? { min: -100, max: 0 }), H - 6, 6);
  const onsetX = x(Date.parse(onset));
  return (
    <section className={panel.panel} aria-labelledby="weather-title">
      <h2 id="weather-title" className="label">
        NASA OMNI · Kp and Dst
      </h2>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        className={styles.chart}
        role="img"
        aria-label="Hourly Kp and Dst over the quiet baseline and the storm"
      >
        <line x1={onsetX} x2={onsetX} y1={0} y2={H} className={styles.onset} vectorEffect="non-scaling-stroke" />
        <path d={linePath(t, weather.kp, x, kpY)} className={styles.kp} vectorEffect="non-scaling-stroke" />
        <path d={linePath(t, weather.dst_nt, x, dstY)} className={styles.dst} vectorEffect="non-scaling-stroke" />
      </svg>
      <div className={panel.legendRow}>
        <span>
          <span className={`${panel.key} ${styles.keyKp}`} aria-hidden="true" />
          Kp (0–9)
        </span>
        <span>
          <span className={`${panel.key} ${styles.keyDst}`} aria-hidden="true" />
          Dst {dstData ? `(${fmtNum(dstData.min, 0)} to ${fmtNum(dstData.max, 0)} nT)` : ""}
        </span>
        <span>{weather.source}</span>
      </div>
    </section>
  );
}
