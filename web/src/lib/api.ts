import type { components } from "./api-types";

export type Fleet = components["schemas"]["Fleet"];
export type FlightSummary = components["schemas"]["FlightSummary"];
export type FlightDetail = components["schemas"]["FlightDetail"];
export type GhostSeries = components["schemas"]["GhostSeries"];
export type RealSeries = components["schemas"]["RealSeries"];
export type DeltaSeries = components["schemas"]["DeltaSeries"];
export type FlightEvent = components["schemas"]["Event"];
export type GapMap = components["schemas"]["GapMap"];
export type GapCell = components["schemas"]["GapCell"];
export type CorrectionReport = components["schemas"]["CorrectionReport"];
export type NextBest = components["schemas"]["NextBest"];
export type Debrief = components["schemas"]["Debrief"];
export type Fact = components["schemas"]["Fact"];
export type OrbitsStatus = components["schemas"]["OrbitsStatus"];
export type OrbitFleet = components["schemas"]["OrbitFleet"];
export type OrbitObjectSummary = components["schemas"]["OrbitObjectSummary"];
export type GapSeries = components["schemas"]["GapSeries"];
export type SpaceWeatherSeries = components["schemas"]["SpaceWeatherSeries"];
export type Provenance = components["schemas"]["Provenance"];
export type EventTiming = components["schemas"]["EventTiming"];
export type TimedEvent = components["schemas"]["TimedEvent"];
export type DescentRate = components["schemas"]["DescentRate"];
export type Fingerprint = components["schemas"]["Fingerprint"];
export type FleetFingerprint = components["schemas"]["FleetFingerprint"];
export type FleetBand = components["schemas"]["FleetBand"];
export type BandCoverage = components["schemas"]["BandCoverage"];
export type GeoPoint = components["schemas"]["GeoPoint"];
export type ObjectEphemeris = components["schemas"]["ObjectEphemeris"];
export type DensityReport = components["schemas"]["DensityReport"];
export type ObjectDensity = components["schemas"]["ObjectDensity"];
export type ObjectDecay = components["schemas"]["ObjectDecay"];
export type DecayBin = components["schemas"]["DecayBin"];
export type LaunchTime = components["schemas"]["LaunchTime"];
export type AccelDensity = components["schemas"]["AccelDensity"];
export type WeatherGhost = components["schemas"]["WeatherGhost"];
export type OpenMctDictionary = components["schemas"]["OpenMctDictionary"];

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
/** Static demo: the API's GET responses exported as files (`asteria export-static`). */
export const STATIC_API = process.env.NEXT_PUBLIC_STATIC_API === "1";
/** Site path prefix when served below a domain root (e.g. GitHub Pages: /asteria). */
export const BASE_PATH = (process.env.NEXT_PUBLIC_BASE_PATH ?? "").replace(/\/$/, "");

/** URL of an API path; in the static demo each path is a file with `ext` appended. */
export function apiUrl(path: string, ext = ".json"): string {
  return STATIC_API ? `${API_URL}${path}${ext}` : `${API_URL}${path}`;
}

export class ApiError extends Error {
  constructor(
    readonly path: string,
    readonly status: number,
  ) {
    super(`${path} → HTTP ${status}`);
  }
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(apiUrl(path), { signal, cache: "no-store" });
  if (!response.ok) throw new ApiError(path, response.status);
  return (await response.json()) as T;
}
