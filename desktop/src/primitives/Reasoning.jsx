import { useEffect, useRef, useState } from "react";

import Icon from "./Icon.jsx";
import Reveal from "./Reveal.jsx";
import styles from "./Reasoning.module.css";
import { thoughtLabel } from "../../../common/reasoningLabel.mjs";
import { lastLine } from "../lib/reasoningTimeline.js";
import { toolIcon } from "../lib/toolSteps.js";

export { thoughtLabel };

function paragraphs(text) {
  return String(text || "").split("\n").map((s) => s.trim()).filter(Boolean);
}

export default function Reasoning({ text, seconds, streaming = false, answered = false, timeline = null }) {
  const [open, setOpen] = useState(false);
  const bodyRef = useRef(null);
  const hasText = !!String(text || "").trim();

  useEffect(() => {
    if (answered) setOpen(false);
  }, [answered]);

  useEffect(() => {
    const el = bodyRef.current;
    if (streaming && open && el) el.scrollTop = el.scrollHeight;
  }, [text, open, streaming]);

  if (!streaming && !hasText && !(seconds >= 1)) return null;

  const livePeek = lastLine(text);
  const label = streaming ? "Thinking…" : thoughtLabel(seconds);
  const labelNode = <span className={streaming ? styles.shimmer : styles.label}>{label}</span>;
  const peekNode = streaming && !open && livePeek ? <span className={styles.peek}>{livePeek}</span> : null;

  if (!hasText) {
    return (
      <div className={styles.reasoning}>
        <div
          className={`${styles.row} ${styles.rowStatic}`}
          role={streaming ? "status" : undefined}
          aria-live={streaming ? "polite" : undefined}
        >
          <Icon name="chevron-right" size={14} className={`${styles.chev} ${streaming ? "" : styles.chevIdle}`} />
          {labelNode}
        </div>
      </div>
    );
  }

  return (
    <div className={styles.reasoning}>
      <button
        type="button"
        className={`${styles.row} ${streaming ? styles.rowLive : ""}`}
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <Icon name="chevron-right" size={14} className={`${styles.chev} ${open ? styles.chevOpen : ""}`} />
        {labelNode}
        {peekNode}
      </button>
      <Reveal open={open}>
        <div className={styles.body} ref={bodyRef}>
          {(timeline?.length ? timeline : [{ kind: "text", text }]).map((item, i) =>
            item.kind === "tools" ? (
              <div key={i} className={styles.stepMark}>
                {item.names.map((name, j) => (
                  <span key={j} className={styles.stepName}>
                    <Icon name={toolIcon(name)} size={11} />
                    {name}
                  </span>
                ))}
              </div>
            ) : (
              paragraphs(item.text).map((p, j) => (
                <p key={`${i}-${j}`} className={styles.para}>{p}</p>
              ))
            ),
          )}
        </div>
      </Reveal>
    </div>
  );
}
