/**
 * Everything the console derives from one FlightDetail, as pure functions.
 * All times are on the ghost clock: real samples are shifted by
 * `delta.real_time_shift_s` (liftoff alignment), exactly as the engine did.
 */
import type { FlightDetail, FlightEvent, GhostSeries } from "./api";
import { interpAt, resample, shiftTime } from "./series";

export type Mode = "physics" | "corrected";

export interface StateRow {
  key: string;
  label: string;
  unit: string;
  digits: number;
  ghost: number | null;
  real: number | null;
  delta: number | null;
  realNote?: string;
}

export function model(detail: FlightDetail, mode: Mode): GhostSeries {
  return mode === "corrected" && detail.corrected ? detail.corrected : detail.ghost;
}

export function realOnGhostClock(detail: FlightDetail): number[] {
  return shiftTime(detail.real.t, detail.delta.real_time_shift_s);
}

function channel(detail: FlightDetail, key: string) {
  return detail.real.channels[key] ?? null;
}

export function stateAt(detail: FlightDetail, t: number, mode: Mode): StateRow[] {
  const g = model(detail, mode);
  const rt = realOnGhostClock(detail);
  const at = (series: readonly (number | null)[]) => interpAt(g.t, series, t);
  const real = (key: string) => {
    const ch = channel(detail, key);
    return ch ? interpAt(rt, ch.values, t) : null;
  };
  const diff = (a: number | null, b: number | null) => (a === null || b === null ? null : a - b);
  const q = at(g.dynamic_pressure);

  // ALT and VZ use the engine's own full-resolution real-on-ghost-grid values,
  // so the Δ on screen is the Δ the API publishes.
  const d = detail.delta;
  const realVzGrid = d.vz.map((dv, i) => {
    const gv = interpAt(detail.ghost.t, detail.ghost.vz, d.t[i]);
    return dv === null || gv === null ? null : dv + gv;
  });
  const ghostAlt = at(g.altitude);
  const realAlt = interpAt(d.t, d.real_altitude, t);
  const ghostVz = at(g.vz);
  const realVz = interpAt(d.t, realVzGrid, t);
  const rows: StateRow[] = [
    { key: "alt", label: "ALT", unit: "m", digits: 1, ghost: ghostAlt, real: realAlt, delta: diff(realAlt, ghostAlt) },
    {
      key: "vz",
      label: "VZ",
      unit: "m/s",
      digits: 1,
      ghost: ghostVz,
      real: realVz,
      delta: diff(realVz, ghostVz),
      realNote: "derived from logged altitude",
    },
  ];
  const ghostSpeed = at(g.speed);
  const loggedSpeed = real("speed_logged");
  rows.push({
    key: "speed",
    label: "SPEED",
    unit: "m/s",
    digits: 1,
    ghost: ghostSpeed,
    real: loggedSpeed,
    delta: diff(loggedSpeed, ghostSpeed),
    realNote: loggedSpeed === null ? "not logged" : channel(detail, "speed_logged")?.name,
  });
  if (channel(detail, "vz_logged")) {
    rows.push({
      key: "vz_logged",
      label: "VZ LOG",
      unit: "m/s",
      digits: 1,
      ghost: null,
      real: real("vz_logged"),
      delta: null,
      realNote: channel(detail, "vz_logged")?.name,
    });
  }
  if (channel(detail, "accel_logged")) {
    rows.push({
      key: "accel",
      label: "ACCEL",
      unit: "m/s²",
      digits: 1,
      ghost: null,
      real: real("accel_logged"),
      delta: null,
      realNote: channel(detail, "accel_logged")?.name,
    });
  }
  rows.push(
    { key: "mach", label: "MACH", unit: "", digits: 3, ghost: at(g.mach), real: null, delta: null, realNote: "not logged" },
    { key: "q", label: "Q", unit: "kPa", digits: 2, ghost: q === null ? null : q / 1000, real: null, delta: null, realNote: "not logged" },
  );
  return rows;
}

export interface Charts {
  t: number[];
  ghostAlt: (number | null)[];
  realAlt: (number | null)[];
  correctedAlt: (number | null)[] | null;
  ghostVz: (number | null)[];
  realVz: (number | null)[];
  ghostSpeed: (number | null)[];
  loggedSpeed: (number | null)[] | null;
  residual: (number | null)[];
}

/** Everything on the delta grid (the ghost's own time grid). */
export function charts(detail: FlightDetail, mode: Mode): Charts {
  const t = detail.delta.t;
  const rt = realOnGhostClock(detail);
  const corrected = detail.corrected ? resample(detail.corrected.t, detail.corrected.altitude, t) : null;
  const realAlt = detail.delta.real_altitude;
  const residual =
    mode === "corrected" && corrected
      ? realAlt.map((r, i) => (r === null || corrected[i] === null ? null : r - (corrected[i] as number)))
      : detail.delta.altitude;
  const speed = detail.real.channels["speed_logged"];
  return {
    t,
    ghostAlt: detail.delta.ghost_altitude,
    realAlt,
    correctedAlt: mode === "corrected" ? corrected : null,
    ghostVz: resample(detail.ghost.t, detail.ghost.vz, t),
    realVz: resample(rt, detail.real.channels["vz"].values, t),
    ghostSpeed: resample(detail.ghost.t, detail.ghost.speed, t),
    loggedSpeed: speed ? resample(rt, speed.values, t) : null,
    residual,
  };
}

export function timelineEvents(detail: FlightDetail): FlightEvent[] {
  const realApogee: FlightEvent = {
    name: "Apogee (real)",
    t: detail.summary.apogee.real_time_s + detail.delta.real_time_shift_s,
    source: "real",
    detail: "Peak of the published log",
  };
  return [...detail.events, realApogee].sort((a, b) => a.t - b.t);
}

export function flightEnd(detail: FlightDetail): number {
  const g = detail.ghost.t;
  const rt = realOnGhostClock(detail);
  return Math.max(g[g.length - 1], rt[rt.length - 1]);
}

export function flightStart(detail: FlightDetail): number {
  return Math.min(0, realOnGhostClock(detail)[0]);
}
