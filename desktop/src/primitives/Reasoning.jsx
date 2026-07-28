import { useEffect, useRef, useState } from "react";

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

export default function Reasoning({ text, seconds, streaming = false, flat = false }) {
  if (!streaming && !String(text || "").trim()) return null;
  return streaming
    ? <Thinking text={text} flat={flat} />
    : <Finished text={text} seconds={seconds} flat={flat} />;
}

function Thinking({ text, flat }) {
  const boxRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, []);
  useEffect(() => {
    const el = boxRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [text, open]);
  const lines = toLines(text);
  const lastLine = lines[lines.length - 1] ?? "";
  return (
    <div className={flat ? styles.flat : styles.trace}>
      <button
        type="button"
        className={`${styles.disclosure} ${styles.live}`}
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={open ? "Collapse reasoning" : "Expand reasoning"}
      >
        <CaretIcon className={open ? styles.chevOpen : styles.chev} />
        <span className={styles.thinkingLabel}>thinking · {elapsed}s</span>
        {!open && lastLine && <span className={styles.peek}>{lastLine}</span>}
      </button>
      {open && (
        <div className={styles.box} ref={boxRef} aria-hidden="true">
          {lines.map((r, i) => (
            <div key={i} className={styles.line}>{r}</div>
          ))}
        </div>
      )}
    </div>
  );
}

function Finished({ text, seconds, flat }) {
  const [open, setOpen] = useState(false);
  const lines = toLines(text);
  const lastLine = lines[lines.length - 1] ?? "";
  const label = flat
    ? (seconds >= 1 ? `thinking · ${fmtDuration(seconds)}` : "thinking")
    : thoughtLabel(seconds);
  return (
    <div className={flat ? styles.flat : styles.trace}>
      <button
        type="button"
        className={flat ? `${styles.disclosure} ${styles.live}` : styles.disclosure}
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={open ? "Collapse reasoning" : "Expand reasoning"}
      >
        <CaretIcon className={open ? styles.chevOpen : styles.chev} />
        <span className={flat ? styles.thinkingLabel : styles.thoughtLabel}>{label}</span>
        {flat && !open && lastLine && <span className={styles.peek}>{lastLine}</span>}
      </button>
      {open && (
        <div className={styles.full}>
          {lines.map((r, i) => (
            <div key={i} className={styles.line}>{r}</div>
          ))}
        </div>
      )}
    </div>
  );
}
