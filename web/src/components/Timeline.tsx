"use client";

import { useEffect, useRef, useState } from "react";

import type { FlightDetail } from "@/lib/api";
import { timelineEvents } from "@/lib/flightView";
import { fmtNum } from "@/lib/format";

import styles from "./Timeline.module.css";

const SPEEDS = [1, 4, 16] as const;

interface Props {
  detail: FlightDetail;
  span: { start: number; end: number };
  cursor: number;
  onCursor: (t: number) => void;
}

/** Event chips on the shared clock, a scrubber, and real-time replay at 1×/4×/16×. */
export function Timeline({ detail, span, cursor, onCursor }: Props) {
  const events = timelineEvents(detail);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(4);
  const cursorRef = useRef(cursor);
  useEffect(() => {
    cursorRef.current = cursor;
  }, [cursor]);

  useEffect(() => {
    if (!playing) return;
    let frame = 0;
    let last = performance.now();
    const step = (now: number) => {
      const next = cursorRef.current + ((now - last) / 1000) * speed;
      last = now;
      if (next >= span.end) {
        onCursor(span.end);
        setPlaying(false);
        return;
      }
      onCursor(next);
      frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [playing, speed, span.end, onCursor]);

  const pct = (t: number) => ((t - span.start) / (span.end - span.start)) * 100;
  return (
    <section className={styles.timeline} aria-label="Event timeline">
      <button
        type="button"
        className={styles.play}
        aria-label={playing ? "Pause replay" : "Play replay"}
        onClick={() => {
          if (!playing && cursor >= span.end) onCursor(span.start);
          setPlaying((p) => !p);
        }}
      >
        {playing ? (
          <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
            <rect x="6" y="4" width="4" height="16" fill="currentColor" />
            <rect x="14" y="4" width="4" height="16" fill="currentColor" />
          </svg>
        ) : (
          <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M7 4l13 8-13 8z" fill="currentColor" />
          </svg>
        )}
      </button>
      <div className={styles.track}>
        <ol className={styles.events}>
          {events.map((e) => (
            <li key={`${e.name}-${e.t}`} style={{ left: `${pct(e.t)}%` }}>
              <button
                type="button"
                className={e.source === "real" ? styles.eventReal : styles.event}
                title={`${e.detail} · T+${fmtNum(e.t, 2)} s (${e.source})`}
                onClick={() => onCursor(e.t)}
              >
                {e.name}
              </button>
            </li>
          ))}
        </ol>
        <label htmlFor="met-scrub" className="visually-hidden">
          Mission elapsed time
        </label>
        <input
          id="met-scrub"
          type="range"
          className={styles.range}
          min={span.start}
          max={span.end}
          step={0.05}
          value={cursor}
          onChange={(e) => onCursor(Number(e.target.value))}
        />
      </div>
      <div className={styles.readout}>T+ {fmtNum(cursor, 2)} s</div>
      <div role="group" aria-label="Replay speed" className={styles.speeds}>
        {SPEEDS.map((s) => (
          <button
            key={s}
            type="button"
            aria-pressed={speed === s}
            className={speed === s ? styles.speedOn : styles.speed}
            onClick={() => setSpeed(s)}
          >
            {s}×
          </button>
        ))}
      </div>
    </section>
  );
}
