"use client";

import { useState } from "react";

import type { Fleet, FlightDetail } from "@/lib/api";
import { fmtMet, fmtNum, shortHash } from "@/lib/format";
import type { Loadable } from "@/lib/useApi";

import { ProvenancePanel } from "./ProvenancePanel";
import styles from "./TopBar.module.css";

export type Tab = "rockets" | "orbits";

interface Props {
  tab: Tab;
  onTab: (t: Tab) => void;
  fleet: Loadable<Fleet>;
  selectedId: string | null;
  onSelect: (id: string) => void;
  detail: FlightDetail | null;
  cursor: number;
}

export function TopBar({ tab, onTab, fleet, selectedId, onSelect, detail, cursor }: Props) {
  const [showProvenance, setShowProvenance] = useState(false);
  const summary = detail?.summary;
  return (
    <header className={styles.bar}>
      <div className={styles.brand}>
        <span className={styles.wordmark}>ASTERIA</span>
        <span className="label">Flight console</span>
      </div>

      {tab === "rockets" && (
        <div className={styles.mission}>
          <div className={styles.picker}>
            <label htmlFor="flight-picker" className="label">
              Flight
            </label>
            <select
              id="flight-picker"
              className={styles.select}
              value={selectedId ?? ""}
              disabled={fleet.state !== "ready"}
              onChange={(e) => onSelect(e.target.value)}
            >
              {fleet.state === "ready" &&
                fleet.data.flights.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name} · {f.event}
                  </option>
                ))}
            </select>
          </div>
          {summary && (
            <>
              <Field label="Mission">
                <span data-testid="mission-name">{summary.name}</span>
              </Field>
              <Field label="Team" title={summary.team}>
                {summary.team}
              </Field>
              <Field label="MET">{fmtMet(cursor)}</Field>
              <Field label="Site">
                {fmtNum(summary.launch_site.latitude_deg, 4)}°, {fmtNum(summary.launch_site.longitude_deg, 4)}° ·{" "}
                {fmtNum(summary.launch_site.elevation_m, 0)} m
              </Field>
            </>
          )}
        </div>
      )}

      <div className={styles.spacer} />

      <div role="tablist" aria-label="Showcase" className={styles.tabs}>
        {(["rockets", "orbits"] as const).map((t) => (
          <button
            key={t}
            role="tab"
            type="button"
            aria-selected={tab === t}
            className={tab === t ? styles.tabActive : styles.tab}
            onClick={() => onTab(t)}
          >
            {t === "rockets" ? "Rockets" : "Orbits · Storm Ghost"}
          </button>
        ))}
      </div>

      {fleet.state === "ready" && (
        <button
          type="button"
          className={styles.chip}
          data-testid="provenance-chip"
          aria-expanded={showProvenance}
          onClick={() => setShowProvenance((v) => !v)}
        >
          RocketPy {fleet.data.provenance.tag} · {shortHash(fleet.data.provenance.commit)}
        </button>
      )}
      {showProvenance && fleet.state === "ready" && (
        <ProvenancePanel fleet={fleet.data} detail={detail} onClose={() => setShowProvenance(false)} />
      )}
    </header>
  );
}

function Field({ label, title, children }: { label: string; title?: string; children: React.ReactNode }) {
  return (
    <div className={styles.field}>
      <div className="label">{label}</div>
      <div className={styles.value} title={title}>
        {children}
      </div>
    </div>
  );
}
