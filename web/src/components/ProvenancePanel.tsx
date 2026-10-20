"use client";

import { useEffect } from "react";

import type { Fleet, FlightDetail } from "@/lib/api";
import { shortHash } from "@/lib/format";

import styles from "./ProvenancePanel.module.css";

interface Props {
  fleet: Fleet;
  detail: FlightDetail | null;
  onClose: () => void;
}

/** Where every number on screen came from: pinned commit, files and their SHA-256. */
export function ProvenancePanel({ fleet, detail, onClose }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const p = fleet.provenance;
  return (
    <section className={styles.panel} aria-label="Provenance">
      <div className={styles.head}>
        <h2 className="label">Provenance</h2>
        <button type="button" className={styles.close} onClick={onClose} aria-label="Close provenance">
          ×
        </button>
      </div>
      <dl className={styles.facts}>
        <dt>Source</dt>
        <dd>
          <a href={`${p.repo.replace(/\.git$/, "")}/tree/${p.commit}`} target="_blank" rel="noreferrer">
            RocketPy {p.tag}
          </a>{" "}
          · commit <span className="mono">{p.commit}</span>
        </dd>
        <dt>Physics</dt>
        <dd>rocketpy {p.rocketpy_version}</dd>
        <dt>Built</dt>
        <dd>
          {p.generated_at} · engine {p.engine_version}
        </dd>
      </dl>

      {detail && (
        <>
          <h3 className="label">{detail.summary.name}: files used</h3>
          <p className={styles.note}>
            Ghost built by executing <span className="mono">{detail.provenance.notebook}</span> as published.
          </p>
          <table className={styles.files}>
            <caption className="visually-hidden">Source files for {detail.summary.name}</caption>
            <thead>
              <tr>
                <th scope="col">File</th>
                <th scope="col">SHA-256</th>
              </tr>
            </thead>
            <tbody>
              {detail.provenance.files.map((f) => (
                <tr key={f.path}>
                  <td className="mono">{f.path}</td>
                  <td className="mono" title={f.sha256}>
                    {shortHash(f.sha256, 12)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {detail.real.raw_source.keep_until_s !== null && (
            <p className={styles.note}>
              <strong>Declared cutoff</strong> at t ={" "}
              <span className="mono">{detail.real.raw_source.keep_until_s} s</span>:{" "}
              {detail.real.raw_source.keep_until_reason}
            </p>
          )}
        </>
      )}

      <h3 className="label">Not used, and why</h3>
      <ul className={styles.excluded}>
        {fleet.excluded.map((e) => (
          <li key={e.notebook}>
            <span className="mono">{e.notebook.split("/").pop()}</span>: {e.reason}
          </li>
        ))}
      </ul>
    </section>
  );
}
