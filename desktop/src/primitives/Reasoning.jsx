import { useEffect, useRef, useState } from "react";

import Activity from "./Activity.jsx";
import { CaretIcon } from "./icons.jsx";
import styles from "./Reasoning.module.css";

function fmtDuration(s) {
  const n = Math.round(s || 0);
  if (n < 60) return `${n}s`;
  const m = Math.floor(n / 60);
  const r = n % 60;
  return r ? `${m}m ${r}s` : `${m}m`;
}

function toLines(text) {
  return String(text || "").split("\n").map((s) => s.trimEnd()).filter((s) => s.trim());
}

// "Thought for Ns" only with a real duration; bare "Thought" when reasoned_s is missing/0 (old sessions) so it never reads "Thought for 0s".
export function thoughtLabel(seconds) {
  return seconds >= 1 ? `Thought for ${fmtDuration(seconds)}` : "Thought";
}

export default function Reasoning({ text, seconds, streaming = false }) {
  if (!String(text || "").trim()) return null;
  return streaming ? <Thinking text={text} /> : <Finished text={text} seconds={seconds} />;
}

function Thinking({ text }) {
  const boxRef = useRef(null);
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, []);
  useEffect(() => {
    const el = boxRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [text]);
  return (
    <div className={styles.trace}>
      <div className={styles.head}>
        <Activity size="md" tint="var(--ink-3)" />
        <span className={styles.thinkingLabel}>thinking · {elapsed}s</span>
      </div>
      <div className={styles.box} ref={boxRef} aria-hidden="true">
        {toLines(text).map((r, i) => (
          <div key={i} className={styles.line}>{r}</div>
        ))}
      </div>
    </div>
  );
}

function Finished({ text, seconds }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={styles.trace}>
      <button
        type="button"
        className={styles.disclosure}
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={open ? "Collapse reasoning" : "Expand reasoning"}
      >
        <CaretIcon className={open ? styles.chevOpen : styles.chev} />
        <span className={styles.thoughtLabel}>{thoughtLabel(seconds)}</span>
      </button>
      {open && (
        <div className={styles.full}>
          {toLines(text).map((r, i) => (
            <div key={i} className={styles.line}>{r}</div>
          ))}
        </div>
      )}
    </div>
  );
}
