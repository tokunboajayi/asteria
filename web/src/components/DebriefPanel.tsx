"use client";

import { useState } from "react";

import type { Debrief } from "@/lib/api";
import type { Loadable } from "@/lib/useApi";

import { PanelStatus } from "./PanelStatus";
import styles from "./Panels.module.css";

interface Props {
  debrief: Loadable<Debrief>;
  flightId: string;
}

/** Grounded debrief: every sentence cites the numbered facts its numbers come from. */
export function DebriefPanel({ debrief, flightId }: Props) {
  const [active, setActive] = useState<string | null>(null);
  if (debrief.state !== "ready" || debrief.data.flight_id !== flightId) {
    return <PanelStatus title="Flight debrief" state={debrief} />;
  }
  const d = debrief.data;
  const facts = new Map(d.facts.map((f) => [f.id, f]));
  return (
    <section className={styles.panel} aria-labelledby="debrief-title">
      <div className={styles.head}>
        <h2 id="debrief-title" className="label">
          Flight debrief
        </h2>
        <span className={d.validation.passed ? styles.tagGo : styles.tagCaution}>
          {d.validation.passed ? "Every number checked" : `${d.validation.rejected} sentence(s) rejected`}
        </span>
      </div>
      <ol className={styles.sentences}>
        {d.sentences.map((s) => (
          <li key={s.text}>
            {s.text}
            {s.fact_ids.map((id) => (
              <button
                key={id}
                type="button"
                className={styles.cite}
                aria-pressed={active === id}
                aria-label={`Fact ${id}: ${facts.get(id)?.label ?? "unknown"}`}
                title={`${facts.get(id)?.label}: ${facts.get(id)?.display} · source ${facts.get(id)?.source}`}
                onClick={() => setActive(active === id ? null : id)}
              >
                {id}
              </button>
            ))}
          </li>
        ))}
      </ol>
      <details>
        <summary className="label">Facts packet ({d.facts.length})</summary>
        <ul className={styles.factList}>
          {d.facts.map((f) => (
            <li key={f.id} className={active === f.id ? styles.factActive : undefined}>
              {f.id} · {f.label}: {f.display} <span title={f.source}>· {f.source}</span>
            </li>
          ))}
        </ul>
      </details>
      <p className={styles.note}>
        Written by {d.generator === "template" ? "code from the facts" : "a language model"}; a sentence whose
        numbers are not in its cited facts is rejected, never repaired.
      </p>
    </section>
  );
}
