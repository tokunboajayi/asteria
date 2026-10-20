"use client";

import { useEffect, useState } from "react";

import { getJson } from "./api";

export type Loadable<T> =
  | { state: "loading" }
  | { state: "error"; message: string }
  | { state: "ready"; data: T };

/** Fetch one API path; refetches when `path` changes, aborts stale requests. */
export function useApi<T>(path: string | null): Loadable<T> {
  const [result, setResult] = useState<Loadable<T>>({ state: "loading" });
  useEffect(() => {
    if (path === null) return;
    const controller = new AbortController();
    setResult({ state: "loading" });
    getJson<T>(path, controller.signal)
      .then((data) => setResult({ state: "ready", data }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setResult({ state: "error", message: error instanceof Error ? error.message : String(error) });
      });
    return () => controller.abort();
  }, [path]);
  return result;
}
