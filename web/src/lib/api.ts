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
export type Provenance = components["schemas"]["Provenance"];

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    readonly path: string,
    readonly status: number,
  ) {
    super(`${path} → HTTP ${status}`);
  }
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { signal, cache: "no-store" });
  if (!response.ok) throw new ApiError(path, response.status);
  return (await response.json()) as T;
}
