"use client";

import { useMemo, useState } from "react";

import type {
  CorrectionReport,
  Debrief,
  Fleet,
  FleetFingerprint,
  FlightDetail,
  GapMap,
  NextBest,
  OrbitsStatus,
} from "@/lib/api";
import { flightEnd, flightStart, type Mode } from "@/lib/flightView";
import { useApi, type Loadable } from "@/lib/useApi";

import styles from "./Console.module.css";
import { CorrectionPanel } from "./CorrectionPanel";
import { DebriefPanel } from "./DebriefPanel";
import { FingerprintPanel } from "./FingerprintPanel";
import { GapMapPanel } from "./GapMapPanel";
import { GlobeView } from "./GlobeView";
import { NextBestPanel } from "./NextBestPanel";
import { OrbitsPanel } from "./OrbitsPanel";
import { StatePanel } from "./StatePanel";
import { StripCharts } from "./StripCharts";
import { Timeline } from "./Timeline";
import { TimingPanel } from "./TimingPanel";
import { TopBar, type Tab } from "./TopBar";

/** The whole console. Owns selection, mode and the shared cursor time; panels only render. */
export function Console() {
  const [tab, setTab] = useState<Tab>("rockets");
  const fleet = useApi<Fleet>("/api/rockets/fleet");
  const [chosenId, setChosenId] = useState<string | null>(null);
  const selectedId = chosenId ?? (fleet.state === "ready" ? (fleet.data.flights[0]?.id ?? null) : null);

  const detail = useApi<FlightDetail>(selectedId ? `/api/rockets/flights/${selectedId}` : null);
  const debrief = useApi<Debrief>(selectedId ? `/api/rockets/flights/${selectedId}/debrief` : null);
  const gap = useApi<GapMap>("/api/rockets/gapmap");
  const correction = useApi<CorrectionReport>("/api/rockets/correction");
  const nextBest = useApi<NextBest>("/api/rockets/nextbest");
  const fingerprint = useApi<FleetFingerprint>("/api/rockets/fingerprint");
  const orbits = useApi<OrbitsStatus>("/api/orbits/status");

  const [mode, setMode] = useState<Mode>("physics");
  const [cursor, setCursor] = useState(0);
  const [replay, setReplay] = useState(false);

  const ready = detail.state === "ready" && detail.data.summary.id === selectedId ? detail.data : null;
  const span = useMemo(() => (ready ? { start: flightStart(ready), end: flightEnd(ready) } : null), [ready]);

  // A new flight starts the cursor at the ghost's first gap-relevant moment: liftoff.
  const liftoff = ready ? ready.diagnostics.ghost_liftoff_s : 0;
  const [cursorFlight, setCursorFlight] = useState<string | null>(null);
  if (ready && cursorFlight !== ready.summary.id) {
    setCursorFlight(ready.summary.id);
    setCursor(liftoff);
    setReplay(false);
  }

  return (
    <div className={styles.console}>
      <TopBar
        tab={tab}
        onTab={setTab}
        fleet={fleet}
        selectedId={selectedId}
        onSelect={(id) => setChosenId(id)}
        detail={ready}
        cursor={cursor}
      />
      {tab === "orbits" ? (
        <OrbitsPanel status={orbits} />
      ) : (
        <RocketsView
          fleet={fleet}
          detail={detail}
          ready={ready}
          span={span}
          mode={mode}
          onMode={setMode}
          cursor={cursor}
          onCursor={setCursor}
          replay={replay}
          onReplay={setReplay}
          debrief={debrief}
          gap={gap}
          correction={correction}
          nextBest={nextBest}
          fingerprint={fingerprint}
        />
      )}
    </div>
  );
}

interface RocketsViewProps {
  fleet: Loadable<Fleet>;
  detail: Loadable<FlightDetail>;
  ready: FlightDetail | null;
  span: { start: number; end: number } | null;
  mode: Mode;
  onMode: (m: Mode) => void;
  cursor: number;
  onCursor: (t: number) => void;
  replay: boolean;
  onReplay: (on: boolean) => void;
  debrief: Loadable<Debrief>;
  gap: Loadable<GapMap>;
  correction: Loadable<CorrectionReport>;
  nextBest: Loadable<NextBest>;
  fingerprint: Loadable<FleetFingerprint>;
}

function RocketsView(p: RocketsViewProps) {
  if (p.fleet.state === "error") {
    return <Status kind="error" text={`Could not reach the Asteria API (${p.fleet.message}). Start it with \`asteria serve\`.`} />;
  }
  if (p.detail.state === "error") {
    return <Status kind="error" text={`Could not load this flight (${p.detail.message}).`} />;
  }
  if (!p.ready || !p.span) return <Status kind="loading" text="Loading flight…" />;
  const detail = p.ready;
  const span = p.span;
  return (
    <div className={styles.grid}>
      <aside className={styles.left} aria-label="Vehicle state">
        <StatePanel detail={detail} mode={p.mode} onMode={p.onMode} cursor={p.cursor} />
        <TimingPanel detail={detail} onCursor={p.onCursor} />
      </aside>
      <main className={styles.center}>
        <GlobeView detail={detail} mode={p.mode} cursor={p.cursor} replay={p.replay} />
        <StripCharts detail={detail} mode={p.mode} cursor={p.cursor} span={span} onCursor={p.onCursor} />
        <Timeline
          detail={detail}
          span={span}
          cursor={p.cursor}
          onCursor={p.onCursor}
          replay={p.replay}
          onReplay={p.onReplay}
        />
      </main>
      <aside className={styles.right} aria-label="Analysis">
        <CorrectionPanel report={p.correction} flightId={detail.summary.id} />
        <FingerprintPanel fingerprint={p.fingerprint} flightId={detail.summary.id} />
        <GapMapPanel gap={p.gap} flightId={detail.summary.id} />
        <DebriefPanel debrief={p.debrief} flightId={detail.summary.id} />
        <NextBestPanel nextBest={p.nextBest} />
      </aside>
    </div>
  );
}

function Status({ kind, text }: { kind: "loading" | "error"; text: string }) {
  return (
    <div className={styles.status} role={kind === "error" ? "alert" : "status"}>
      {text}
    </div>
  );
}
