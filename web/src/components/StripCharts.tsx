"use client";

import { useRef } from "react";

import type { FlightDetail } from "@/lib/api";
import { clamp, extent, linePath, padded, scale, symmetric, type Domain } from "@/lib/chart";
import { charts, realOnGhostClock, timelineEvents, type Mode } from "@/lib/flightView";
import { fmtNum } from "@/lib/format";

import styles from "./StripCharts.module.css";

const W = 1000;
const H = 74;

interface Props {
  detail: FlightDetail;
  mode: Mode;
  cursor: number;
  span: { start: number; end: number };
  onCursor: (t: number) => void;
}

interface Line {
  t: readonly number[];
  v: readonly (number | null)[];
  kind: "ghost" | "real" | "corrected" | "gap" | "zero";
}

export function StripCharts({ detail, mode, cursor, span, onCursor }: Props) {
  const c = charts(detail, mode);
  const corrected = mode === "corrected" && c.correctedAlt !== null;
  const rt = realOnGhostClock(detail);
  const realAlt = detail.real.channels["altitude"].values;
  const realVz = detail.real.channels["vz"].values;
  const events = timelineEvents(detail);
  const x = scale({ min: span.start, max: span.end }, 0, W);

  const altLines: Line[] = [
    { t: c.t, v: c.ghostAlt, kind: "ghost" },
    { t: rt, v: realAlt, kind: "real" },
  ];
  if (corrected && c.correctedAlt) altLines.push({ t: c.t, v: c.correctedAlt, kind: "corrected" });

  const residualLabel = corrected
    ? "Δ altitude · real − corrected (held-out correction)"
    : "Δ altitude · real − ghost (physics only)";

  return (
    <section className={styles.charts} aria-label="Strip charts">
      <Chart
        title="Altitude AGL"
        unit="m"
        lines={altLines}
        domain={padded(extent(altLines.map((l) => l.v)) ?? { min: 0, max: 1 })}
        x={x}
        cursor={cursor}
        span={span}
        onCursor={onCursor}
        events={events}
        showEventNames
        aria={`Altitude over time: ghost${corrected ? ", corrected" : ""} and the real log`}
      />
      <Chart
        title="Vertical velocity"
        unit="m/s · real derived"
        lines={[
          { t: c.t, v: c.ghostVz, kind: "ghost" },
          { t: rt, v: realVz, kind: "real" },
        ]}
        domain={padded(extent([c.ghostVz, realVz]) ?? { min: 0, max: 1 })}
        x={x}
        cursor={cursor}
        span={span}
        onCursor={onCursor}
        events={events}
        aria="Vertical velocity over time: ghost and real (derived from logged altitude)"
      />
      <Chart
        title="Residual"
        unit="m"
        testId="residual-label"
        subtitle={residualLabel}
        lines={[
          { t: [span.start, span.end], v: [0, 0], kind: "zero" },
          { t: c.t, v: c.residual, kind: "gap" },
        ]}
        domain={symmetric(extent([c.residual]) ?? { min: -1, max: 1 })}
        x={x}
        cursor={cursor}
        span={span}
        onCursor={onCursor}
        events={events}
        aria={residualLabel}
      />
    </section>
  );
}

interface ChartProps {
  title: string;
  unit: string;
  subtitle?: string;
  testId?: string;
  lines: Line[];
  domain: Domain;
  x: (t: number) => number;
  cursor: number;
  span: { start: number; end: number };
  onCursor: (t: number) => void;
  events: { name: string; t: number; source: string }[];
  showEventNames?: boolean;
  aria: string;
}

function Chart(p: ChartProps) {
  const ref = useRef<SVGSVGElement>(null);
  const y = scale(p.domain, H - 4, 4);
  const toTime = (clientX: number) => {
    const box = ref.current?.getBoundingClientRect();
    if (!box || box.width === 0) return p.cursor;
    const f = clamp((clientX - box.left) / box.width, 0, 1);
    return p.span.start + f * (p.span.end - p.span.start);
  };
  const cx = p.x(clamp(p.cursor, p.span.start, p.span.end));
  return (
    <div className={styles.row}>
      <div className={styles.head}>
        <div className="label">{p.title}</div>
        <div className={styles.unit}>{p.unit}</div>
        <div className={styles.ticks}>
          <span>{fmtNum(p.domain.max, 0)}</span>
          <span>{fmtNum(p.domain.min, 0)}</span>
        </div>
      </div>
      <div className={styles.plot}>
        {p.subtitle && (
          <div className={styles.subtitle} data-testid={p.testId}>
            {p.subtitle}
          </div>
        )}
        <svg
          ref={ref}
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          className={styles.svg}
          role="img"
          aria-label={p.aria}
          onPointerDown={(e) => {
            e.currentTarget.setPointerCapture(e.pointerId);
            p.onCursor(toTime(e.clientX));
          }}
          onPointerMove={(e) => {
            if (e.buttons === 1) p.onCursor(toTime(e.clientX));
          }}
        >
          {p.events.map((ev) => (
            <line
              key={`${ev.name}-${ev.t}`}
              x1={p.x(ev.t)}
              x2={p.x(ev.t)}
              y1={0}
              y2={H}
              className={ev.name.startsWith("Mach 1") ? styles.eventKey : styles.event}
              vectorEffect="non-scaling-stroke"
            />
          ))}
          {p.lines.map((l, i) => (
            <path
              key={i}
              d={linePath(l.t, l.v, p.x, y)}
              className={styles[l.kind]}
              vectorEffect="non-scaling-stroke"
            />
          ))}
          <line x1={cx} x2={cx} y1={0} y2={H} className={styles.cursor} vectorEffect="non-scaling-stroke" />
        </svg>
        {p.showEventNames && (
          <div className={styles.eventNames} aria-hidden="true">
            {p.events.map((ev) => (
              <span
                key={`${ev.name}-${ev.t}`}
                style={{ left: `${(p.x(ev.t) / W) * 100}%` }}
                className={ev.source === "real" ? styles.eventReal : undefined}
              >
                {ev.name}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
