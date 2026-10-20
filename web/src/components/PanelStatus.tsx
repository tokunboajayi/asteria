import type { Loadable } from "@/lib/useApi";

import styles from "./Panels.module.css";

/** Loading / error state for an analysis panel. */
export function PanelStatus({ title, state }: { title: string; state: Loadable<unknown> }) {
  return (
    <section className={styles.panel}>
      <h2 className="label">{title}</h2>
      <p className={styles.note} role={state.state === "error" ? "alert" : "status"}>
        {state.state === "error" ? `Unavailable: ${state.message}` : "Loading…"}
      </p>
    </section>
  );
}
