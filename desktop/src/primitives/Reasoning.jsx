import { useState } from "react";

import { CaretIcon } from "./icons.jsx";
import styles from "./Reasoning.module.css";

function toParagraphs(text) {
  return String(text || "")
    .split(/\n{2,}/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function fmtDuration(s) {
  const n = Math.round(s);
  if (n < 60) return `${n}s`;
  const m = Math.floor(n / 60);
  const r = n % 60;
  return r ? `${m}m ${r}s` : `${m}m`;
}

export default function Reasoning({ text, seconds, streaming = false }) {
  const paras = toParagraphs(text);
  const [open, setOpen] = useState(streaming);
  if (!paras.length) return null;
  const label = streaming
    ? "Reasoning…"
    : seconds >= 1
      ? `Reasoned for ${fmtDuration(seconds)}`
      : "Reasoned";
  return (
    <div className={styles.wrap}>
      <button
        type="button"
        className={styles.head}
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={open ? "Collapse reasoning" : "Expand reasoning"}
      >
        <CaretIcon className={open ? styles.caretOpen : styles.caret} />
        <span className={`${styles.label} ${streaming ? styles.streaming : ""}`}>{label}</span>
      </button>
      {open && (
        <div className={styles.body}>
          {paras.map((p, i) => (
            <p key={i} className={styles.para}>{p}</p>
          ))}
        </div>
      )}
    </div>
  );
}
