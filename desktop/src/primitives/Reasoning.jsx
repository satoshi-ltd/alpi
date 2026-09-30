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

export default function Reasoning({ text, seconds, streaming = false, answered = false, timeline = null, peek = null }) {
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

  if (!streaming && !hasText) return null;

  const items = timeline?.length ? timeline : [{ kind: "text", text }];
  const livePeek = peek ?? lastLine(text);
  const label = streaming ? "Thinking…" : thoughtLabel(seconds);

  return (
    <div className={styles.reasoning}>
      <button
        type="button"
        className={`${styles.row} ${streaming ? styles.rowLive : ""}`}
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={open ? "Collapse reasoning" : "Expand reasoning"}
        disabled={!hasText}
      >
        {hasText && (
          <Icon name="chevron-right" size={12} className={`${styles.chev} ${open ? styles.chevOpen : ""}`} />
        )}
        <span className={streaming ? styles.shimmer : styles.label}>{label}</span>
        {streaming && !open && livePeek && <span className={styles.peek}>{livePeek}</span>}
      </button>
      <Reveal open={open && hasText}>
        <div className={styles.body} ref={bodyRef}>
          {items.map((item, i) =>
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
