"use client";

import { useEffect, useRef, useState } from "react";

import { API_URL } from "@/lib/api";

import controls from "./Controls.module.css";
import styles from "./ExportDialog.module.css";
import panel from "./Panels.module.css";

interface Props {
  name: string;
  /** Path under the API, e.g. /api/export/oem/orbit/25544; null when no OEM can be made. */
  oemPath: string | null;
  /** What the OEM contains, or why there is none. */
  oemNote: string;
  onClose: () => void;
}

const PLUGIN = (base: string) => `// Open MCT plugin: Asteria dictionary + historical telemetry.
// Install with openmct.install(AsteriaPlugin()) before openmct.start().
function AsteriaPlugin() {
  return function install(openmct) {
    const base = '${base}';
    const dict = fetch(base + '/api/openmct/dictionary.json').then((r) => r.json());
    openmct.objects.addRoot({ namespace: 'asteria', key: 'root' });
    openmct.types.addType('asteria.telemetry', { name: 'Asteria telemetry', cssClass: 'icon-telemetry' });
    openmct.objects.addProvider('asteria', {
      get: (id) => dict.then((d) => {
        if (id.key === 'root') return { identifier: id, name: d.name, type: 'folder', location: 'ROOT' };
        const m = d.measurements.find((x) => x.key === id.key);
        return { identifier: id, name: m.name, type: 'asteria.telemetry',
                 telemetry: { values: m.values }, location: 'asteria:root' };
      }),
    });
    openmct.composition.addProvider({
      appliesTo: (o) => o.identifier.namespace === 'asteria' && o.type === 'folder',
      load: () => dict.then((d) => d.measurements.map((m) => ({ namespace: 'asteria', key: m.key }))),
    });
    openmct.telemetry.addProvider({
      supportsRequest: (o) => o.type === 'asteria.telemetry',
      request: (o, opts) =>
        fetch(base + '/api/openmct/telemetry/' + encodeURIComponent(o.identifier.key))
          .then((r) => r.json())
          .then((pts) => pts.filter((p) => p.timestamp >= opts.start && p.timestamp <= opts.end)),
    });
  };
}`;

export function ExportDialog({ name, oemPath, oemNote, onClose }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const [copy, setCopy] = useState<"idle" | "done" | "failed">("idle");

  useEffect(() => {
    const d = ref.current;
    if (d && !d.open) d.showModal();
  }, []);

  const oemUrl = oemPath ? `${API_URL}${oemPath}` : null;
  const file = `${name.replace(/[^A-Za-z0-9]+/g, "_")}.oem`;

  return (
    <dialog ref={ref} className={styles.dialog} aria-labelledby="export-title" onClose={onClose}>
      <div className={controls.headRow}>
        <h2 id="export-title" className="label">
          Export · {name}
        </h2>
        <button type="button" className={controls.button} onClick={() => ref.current?.close()}>
          Close
        </button>
      </div>

      <section className={styles.section}>
        <h3 className="label">CCSDS Orbit Ephemeris Message (502.0-B-2)</h3>
        <p className={panel.note}>{oemNote}</p>
        {oemUrl && (
          <div className={controls.row}>
            <a href={oemUrl} download={file} className={controls.buttonOn} data-testid="oem-download">
              Download {file}
            </a>
            <a href={oemUrl} target="_blank" rel="noreferrer" className={controls.button}>
              View text
            </a>
          </div>
        )}
      </section>

      <section className={styles.section}>
        <h3 className="label">NASA Open MCT</h3>
        <p className={panel.note}>
          A telemetry dictionary in Open MCT&apos;s tutorial format, and historical telemetry per key. Every key in
          the dictionary is served from the published artifacts. If Open MCT runs on another origin, add that
          origin to ASTERIA_WEB_ORIGINS.
        </p>
        <dl className={panel.kv}>
          <dt>Dictionary</dt>
          <dd>
            <code>{API_URL}/api/openmct/dictionary.json</code>
          </dd>
          <dt>Telemetry</dt>
          <dd>
            <code>{API_URL}/api/openmct/telemetry/&lt;key&gt;</code>
          </dd>
        </dl>
        <button
          type="button"
          className={controls.button}
          onClick={() => {
            navigator.clipboard
              .writeText(PLUGIN(API_URL))
              .then(() => setCopy("done"))
              .catch(() => setCopy("failed"));
          }}
        >
          {copy === "done" ? "Plugin copied" : copy === "failed" ? "Copy blocked by the browser" : "Copy Open MCT plugin"}
        </button>
      </section>
    </dialog>
  );
}
