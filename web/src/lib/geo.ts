/**
 * Geographic points for the 3D view, from published series only.
 * Heights are launch-site elevation + altitude AGL (metres above mean sea level).
 */
import type { FlightDetail, GhostSeries } from "./api";
import { interpAt } from "./series";

export interface GeoPoint {
  lon: number;
  lat: number;
  height: number;
}

/** Every sample of a modelled trajectory (ghost or corrected). */
export function modelPath(series: GhostSeries, elevation: number): GeoPoint[] {
  return series.t.map((_, i) => ({
    lon: series.longitude[i],
    lat: series.latitude[i],
    height: elevation + series.altitude[i],
  }));
}

/** Model position at time t (ghost clock); null outside the series. */
export function modelAt(series: GhostSeries, elevation: number, t: number): GeoPoint | null {
  const lat = interpAt(series.t, series.latitude, t);
  const lon = interpAt(series.t, series.longitude, t);
  const alt = interpAt(series.t, series.altitude, t);
  if (lat === null || lon === null || alt === null) return null;
  return { lon, lat, height: elevation + alt };
}

/**
 * The real track: GNSS fixes, each lifted to the logged altitude at the same
 * log time. Null when the log has no position; a fix with no altitude
 * sample around it is skipped, never guessed.
 */
export function realTrack(detail: FlightDetail): GeoPoint[] | null {
  const gnss = detail.real.gnss;
  if (!gnss) return null;
  const alt = detail.real.channels["altitude"];
  const elevation = detail.summary.launch_site.elevation_m;
  const out: GeoPoint[] = [];
  for (let i = 0; i < gnss.t.length; i++) {
    const a = interpAt(detail.real.t, alt.values, gnss.t[i]);
    if (a === null) continue;
    out.push({ lon: gnss.longitude[i], lat: gnss.latitude[i], height: elevation + a });
  }
  return out;
}

/** Real position at ghost-clock time t (log time = t − shift); null if not logged then. */
export function realAt(detail: FlightDetail, t: number): GeoPoint | null {
  const gnss = detail.real.gnss;
  if (!gnss) return null;
  const tl = t - detail.delta.real_time_shift_s;
  const lat = interpAt(gnss.t, gnss.latitude, tl);
  const lon = interpAt(gnss.t, gnss.longitude, tl);
  const alt = interpAt(detail.real.t, detail.real.channels["altitude"].values, tl);
  if (lat === null || lon === null || alt === null) return null;
  return { lon, lat, height: detail.summary.launch_site.elevation_m + alt };
}
