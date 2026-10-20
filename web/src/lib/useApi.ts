"use client";

import { useEffect, useState } from "react";

import { getJson } from "./api";

export type Loadable<T> =
  | { state: "loading" }
  | { state: "error"; message: string }
  | { state: "ready"; data: T };

type Settled<T> = { path: string; result: Exclude<Loadable<T>, { state: "loading" }> };

/**
 * Fetch one API path; refetches when `path` changes and aborts stale requests.
 * State is only set from the request's callbacks; "loading" is derived (the
 * last settled result belongs to a different path), so a stale response can
 * never be shown for the current path.
 */
export function useApi<T>(path: string | null): Loadable<T> {
  const [settled, setSettled] = useState<Settled<T> | null>(null);
  useEffect(() => {
    if (path === null) return;
    const controller = new AbortController();
    getJson<T>(path, controller.signal)
      .then((data) => setSettled({ path, result: { state: "ready", data } }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setSettled({
          path,
          result: { state: "error", message: error instanceof Error ? error.message : String(error) },
        });
      });
    return () => controller.abort();
  }, [path]);
  if (path === null || settled === null || settled.path !== path) return { state: "loading" };
  return settled.result;
}
