/**
 * Mission replay: mission-time compression, flight phase and event callouts at a
 * cursor time. Pure functions of the published flight; nothing here is invented.
 */
import type { FlightDetail } from "./api";
import { timelineEvents } from "./flightView";

/** How long (flight seconds) a callout stays up after its event. */
export const CALLOUT_S = 6;
/** Real-time playback rate per phase: every second of the burn, faster coast, fast descent. */
export const REPLAY_RATES = { boost: 1, coast: 4, descent: 16 } as const;
const BOOST_TAIL_S = 2;

export type Phase = "pad" | "boost" | "coast" | "descent";

function ghostEvent(detail: FlightDetail, name: string): number | null {
  return detail.events.find((e) => e.name === name)?.t ?? null;
}

export function phaseAt(detail: FlightDetail, t: number): Phase {
  const liftoff = detail.diagnostics.ghost_liftoff_s;
  const burnout = ghostEvent(detail, "Burnout") ?? liftoff;
  const apogee = ghostEvent(detail, "Apogee") ?? detail.summary.apogee.ghost_time_s;
  if (t < liftoff) return "pad";
  if (t < burnout) return "boost";
  if (t < apogee) return "coast";
  return "descent";
}

/** Playback rate at t: 1× through the burn (plus a short tail), 4× in coast, 16× after apogee. */
export function replayRate(detail: FlightDetail, t: number): number {
  const burnout = ghostEvent(detail, "Burnout") ?? detail.diagnostics.ghost_liftoff_s;
  const apogee = ghostEvent(detail, "Apogee") ?? detail.summary.apogee.ghost_time_s;
  if (t < burnout + BOOST_TAIL_S) return REPLAY_RATES.boost;
  if (t < apogee + BOOST_TAIL_S) return REPLAY_RATES.coast;
  return REPLAY_RATES.descent;
}

export interface Callout {
  key: string;
  title: string;
  detail: string;
  source: "ghost" | "real";
}

/** The most recent event within CALLOUT_S of t, with its real-vs-ghost timing when measured. */
export function calloutAt(detail: FlightDetail, t: number): Callout | null {
  const recent = timelineEvents(detail).filter((e) => e.t <= t && t - e.t <= CALLOUT_S);
  const e = recent[recent.length - 1];
  if (!e) return null;
  if (e.source === "ghost") {
    return { key: `${e.name}-${e.t}`, title: e.name, detail: `Ghost · ${e.detail}`, source: "ghost" };
  }
  const timed = detail.timing.events.find((x) => `${x.name} (real)` === e.name);
  const dt = timed?.delta_t_s ?? null;
  const when =
    dt === null
      ? "Detected in the real log"
      : Math.abs(dt) < 0.005
        ? "Same moment as the ghost"
        : `${Math.abs(dt).toFixed(2)} s ${dt < 0 ? "before" : "after"} the ghost`;
  return { key: `${e.name}-${e.t}`, title: e.name, detail: `Real · ${when}`, source: "real" };
}
