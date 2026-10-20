"use client";

import type { OrbitsStatus } from "@/lib/api";
import type { Loadable } from "@/lib/useApi";

import styles from "./Panels.module.css";

/** Storm Ghost. Until real tracking data is built, it says so and shows nothing else. */
export function OrbitsPanel({ status }: { status: Loadable<OrbitsStatus> }) {
  return (
    <section className={styles.panel} aria-labelledby="orbits-title" style={{ maxWidth: 760, margin: "24px auto" }}>
      <h2 id="orbits-title" className="label">
        Orbits · Storm Ghost
      </h2>
      {status.state === "loading" && <p className={styles.note}>Loading…</p>}
      {status.state === "error" && (
        <p className={styles.note} role="alert">
          Unavailable: {status.message}
        </p>
      )}
      {status.state === "ready" && !status.data.available && (
        <p className={styles.lead} data-testid="orbits-gated">
          {status.data.reason}
        </p>
      )}
      <p className={styles.note}>
        Storm Ghost propagates a satellite&apos;s orbit from its last element set before a geomagnetic storm (the
        ghost) and compares it with the orbits tracking measured afterwards, alongside NASA space-weather
        indices for the same hours.
      </p>
    </section>
  );
}
