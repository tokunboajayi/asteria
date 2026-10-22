/**
 * The altitude ruler drawn at the launch pad on the 3D view.
 *
 * Every flight logs altitude, but not every flight logs position. The ruler
 * is where reality can always be shown honestly: on a vertical scale at the
 * pad, as an altitude, without pretending to know where the rocket was.
 * All heights are metres above the pad (AGL).
 */
import type { FlightDetail } from "./api";
import { model, realOnGhostClock, type Mode } from "./flightView";
import { interpAt } from "./series";

export interface RulerMark {
  /** Metres above the pad. */
  agl: number;
  label: string;
}

export interface Ruler {
  top: number;
  ticks: RulerMark[];
  model: RulerMark;
  real: RulerMark;
  /** real − model apogee, metres. */
  gap: number;
  modelName: "Ghost" | "Corrected";
}

/** Fraction of the ruler's height kept free of tick labels around each apogee label. */
const CLEARANCE = 0.12;

const STEPS = [50, 100, 200, 250, 500, 1000, 2000, 2500, 5000];

/** A round tick spacing giving about five ticks up to `span`. */
export function tickStep(span: number): number {
  return STEPS.find((s) => span / s <= 6) ?? STEPS[STEPS.length - 1];
}

function maxOf(values: readonly number[]): number {
  return values.reduce((m, v) => (v > m ? v : m), -Infinity);
}

export function buildRuler(detail: FlightDetail, mode: Mode, format: (m: number) => string): Ruler {
  const corrected = mode === "corrected" && Boolean(detail.corrected);
  // One source per number: the engine's apogees, so the 3D view matches every other panel.
  const modelApogee = corrected
    ? (detail.summary.correction?.corrected_apogee_m ?? maxOf(model(detail, mode).altitude))
    : detail.summary.apogee.ghost_m;
  const realApogee = detail.summary.apogee.real_m;
  const highest = Math.max(modelApogee, realApogee);
  const step = tickStep(highest);
  const top = Math.ceil((highest * 1.12) / step) * step;
  // Tick labels near an apogee label would collide with it on screen (the apogee
  // labels are also nudged apart vertically); drop ticks within 12% of the ruler.
  const clear = (agl: number) =>
    Math.abs(agl - modelApogee) > CLEARANCE * top && Math.abs(agl - realApogee) > CLEARANCE * top;
  const ticks: RulerMark[] = [];
  for (let agl = step; agl < top; agl += step) {
    ticks.push({ agl, label: clear(agl) ? `${format(agl)} m` : "" });
  }
  const modelName = corrected ? "Corrected" : "Ghost";
  return {
    top,
    ticks,
    model: { agl: modelApogee, label: `${modelName} ${format(modelApogee)} m` },
    real: { agl: realApogee, label: `Real ${format(realApogee)} m` },
    gap: realApogee - modelApogee,
    modelName,
  };
}

/** Logged altitude (AGL) at ghost-clock time t; null when the log has no sample then. */
export function realAltitudeAt(detail: FlightDetail, t: number): number | null {
  const altitude = detail.real.channels["altitude"];
  if (!altitude) return null;
  return interpAt(realOnGhostClock(detail), altitude.values, t);
}
