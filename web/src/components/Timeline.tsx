"use client";

import { useEffect, useRef, useState } from "react";

import type { FlightDetail } from "@/lib/api";
import { timelineEvents } from "@/lib/flightView";
import { fmtMet, fmtNum } from "@/lib/format";
import { replayRate } from "@/lib/replay";

import styles from "./Timeline.module.css";

const SPEEDS = [1, 4, 16] as const;

interface Props {
  detail: FlightDetail;
  span: { start: number; end: number };
  cursor: number;
  onCursor: (t: number) => void;
  replay: boolean;
  onReplay: (on: boolean) => void;
}

/** Event chips on the shared clock, a scrubber, and real-time replay at 1×/4×/16×. */
export function Timeline({ detail, span, cursor, onCursor, replay, onReplay }: Props) {
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
      // Mission replay compresses time by phase; normal play uses the chosen speed.
      const rate = replay ? replayRate(detail, cursorRef.current) : speed;
      const next = cursorRef.current + ((now - last) / 1000) * rate;
      last = now;
      if (next >= span.end) {
        onCursor(span.end);
        setPlaying(false);
        onReplay(false);
        return;
      }
      onCursor(next);
      frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [playing, speed, span.end, onCursor, replay, detail, onReplay]);

  /** Any manual control ends a mission replay. */
  const manual = (t: number) => {
    if (replay) onReplay(false);
    onCursor(t);
  };

  const pct = (t: number) => ((t - span.start) / (span.end - span.start)) * 100;
  return (
    <section className={styles.timeline} aria-label="Event timeline">
      <button
        type="button"
        className={styles.play}
        aria-label={playing ? "Pause replay" : "Play replay"}
        onClick={() => {
          if (playing && replay) onReplay(false);
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
        <div className={styles.ticks} aria-hidden="true">
          {events.map((e) => (
            <span
              key={`${e.name}-${e.t}`}
              className={e.source === "real" ? styles.tickReal : styles.tick}
              style={{ left: `${pct(e.t)}%` }}
            />
          ))}
        </div>
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
          onChange={(e) => manual(Number(e.target.value))}
        />
        <ol className={styles.events} aria-label="Jump to event">
          {events.map((e) => (
            <li key={`${e.name}-${e.t}`}>
              <button
                type="button"
                className={e.source === "real" ? styles.eventReal : styles.event}
                title={`${e.detail} (${e.source})`}
                onClick={() => manual(e.t)}
              >
                {e.name} <span className={styles.eventTime}>T+{fmtNum(e.t, 1)}</span>
              </button>
            </li>
          ))}
        </ol>
      </div>
      <div className={styles.readout}>{fmtMet(cursor)}</div>
      <button
        type="button"
        className={replay ? styles.replayOn : styles.replay}
        aria-pressed={replay}
        data-testid="mission-replay"
        onClick={() => {
          if (replay) {
            onReplay(false);
            setPlaying(false);
            return;
          }
          onCursor(Math.max(span.start, detail.diagnostics.ghost_liftoff_s - 2));
          onReplay(true);
          setPlaying(true);
        }}
      >
        {replay ? "Stop replay" : "Mission replay"}
      </button>
      <div role="group" aria-label="Replay speed" className={styles.speeds}>
        {SPEEDS.map((s) => (
          <button
            key={s}
            type="button"
            aria-pressed={!replay && speed === s}
            className={!replay && speed === s ? styles.speedOn : styles.speed}
            onClick={() => {
              if (replay) onReplay(false);
              setSpeed(s);
            }}
          >
            {s}×
          </button>
        ))}
      </div>
    </section>
  );
}
