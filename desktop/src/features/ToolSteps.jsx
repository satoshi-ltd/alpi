import { memo, useCallback, useEffect, useState } from "react";

import CodeView from "../primitives/CodeView.jsx";
import IconBtn from "../primitives/IconBtn.jsx";
import Reveal from "../primitives/Reveal.jsx";
import Tip from "../primitives/Tip.jsx";
import { CaretIcon, CopyIcon, Icon } from "../primitives/icons.jsx";
import { useNotify } from "../primitives/Notification.jsx";
import { pluralize } from "../../../common/pluralize.mjs";
import { copyText } from "../lib/clipboard.js";
import { fmtToolDuration, prettyArgs, toolIcon, toolResult, toolSummary } from "../lib/toolSteps.js";
import styles from "./ToolSteps.module.css";

export function toolStatus(t) {
  return t.ok === null || t.ok === undefined ? "running" : t.ok ? "ok" : "fail";
}

function startMs(tool) {
  if (typeof tool.started_at === "number" && Number.isFinite(tool.started_at)) return tool.started_at * 1000;
  if (typeof tool.startedAt === "number") return tool.startedAt;
  return null;
}

function useNow(active) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return undefined;
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(id);
  }, [active]);
  return now;
}

function CopyButton({ text, label }) {
  const notify = useNotify();
  const onCopy = async (e) => {
    e.stopPropagation();
    if (await copyText(text)) notify({ message: "Copied", variant: "success" });
    else notify({ message: "Copy failed", variant: "error" });
  };
  return (
    <Tip text={label} side="up-r" escape>
      <IconBtn aria-label={label} onClick={onCopy} className={styles.copyBtn}>
        <CopyIcon style={{ width: 12, height: 12 }} />
      </IconBtn>
    </Tip>
  );
}

export const ToolStep = memo(function ToolStep({ tool, accent, open: openProp, onToggle }) {
  const status = toolStatus(tool);
  const [own, setOwn] = useState(null);
  const open = openProp ?? own ?? status === "fail";
  const toggle = () => (onToggle ? onToggle(!open) : setOwn(!open));

  const started = startMs(tool);
  const now = useNow(status === "running" && started != null);
  const seconds = status === "running"
    ? (started != null ? Math.max(0, (now - started) / 1000) : null)
    : tool.duration_s;
  const dur = fmtToolDuration(seconds);
  const summary = toolSummary(tool);
  const argsText = prettyArgs(tool.args);
  const result = toolResult(tool);
  const iconColor = status === "fail" ? "var(--c-danger)" : status === "running" ? (accent || "var(--accent)") : "var(--ink-3)";
  const statusText = status === "fail"
    ? (dur ? `failed · ${dur}` : "failed")
    : status === "running" ? `${dur ? `${dur} ` : ""}…` : dur;

  return (
    <div className={`${styles.step} ${styles[`step_${status}`]}`}>
      <button
        type="button"
        className={`${styles.head} ${open ? styles.headOpen : ""}`}
        onClick={toggle}
        aria-expanded={open}
        aria-label={`${tool.name}${summary ? ` ${summary}` : ""}`}
      >
        <Icon name={toolIcon(tool.name)} size={14} color={iconColor} className={styles.icon} />
        <span className={styles.name}>{tool.name}</span>
        <span className={styles.summary}>{summary}</span>
        {statusText && <span className={`tnum ${styles.status}`}>{statusText}</span>}
        <Icon name="chevron-right" size={12} className={`${styles.chev} ${open ? styles.chevOpen : ""}`} />
      </button>
      <Reveal open={open}>
        <div className={styles.detail}>
          {argsText && argsText !== "{}" && (
            <section className={styles.section}>
              <div className={styles.sectionHead}>
                <span>Arguments</span>
                <CopyButton text={argsText} label="Copy arguments" />
              </div>
              <div className={styles.code}>
                <CodeView text={argsText} />
              </div>
            </section>
          )}
          {result ? (
            <section className={styles.section}>
              <div className={styles.sectionHead}>
                <span>
                  {tool.output ? "Output" : "Result"}
                  {result.excerpt && <span className={styles.excerpt}> · excerpt</span>}
                </span>
                <CopyButton text={result.text} label={tool.output ? "Copy output" : "Copy result"} />
              </div>
              <pre className={`${styles.output} ${status === "fail" ? styles.outputFail : ""}`}>{result.text}</pre>
            </section>
          ) : (
            <div className={styles.empty}>{status === "running" ? "Running…" : "No output"}</div>
          )}
        </div>
      </Reveal>
    </div>
  );
});

export const ToolModule = memo(function ToolModule({ tools, accent }) {
  const [bucketChoice, setBucketChoice] = useState(null);
  const [overrides, setOverrides] = useState({});
  const setStep = useCallback((key, value) => setOverrides((prev) => ({ ...prev, [key]: value })), []);
  if (!tools.length) return null;
  const keyOf = (t, i) => t.tool_id ?? `${t.name}:${i}`;
  const isOpen = (t, i) => overrides[keyOf(t, i)] ?? toolStatus(t) === "fail";
  const step = (t, i) => (
    <ToolStep
      key={keyOf(t, i)}
      tool={t}
      accent={accent}
      open={isOpen(t, i)}
      onToggle={(value) => setStep(keyOf(t, i), value)}
    />
  );

  if (tools.length === 1) {
    return <div className={styles.module}>{step(tools[0], 0)}</div>;
  }

  const runningIdx = tools.findIndex((t) => t.ok == null);
  const active = runningIdx >= 0;
  const bucket = tools.map((t, i) => [t, i]).filter(([, i]) => i !== runningIdx);
  const n = bucket.length;
  const noun = pluralize(n, "tool call");
  const failed = bucket.filter(([t]) => toolStatus(t) === "fail").length;
  const expanded = bucketChoice ?? bucket.some(([t, i]) => isOpen(t, i));
  const collapsedLabel = active ? `+${n} previous ${noun}` : `${n} ${noun}`;
  const expandedLabel = active ? "Hide previous tool calls" : "Hide tool calls";
  return (
    <div className={styles.module}>
      <button
        type="button"
        className={styles.bucket}
        onClick={() => setBucketChoice(!expanded)}
        aria-expanded={expanded}
        aria-label={expanded ? expandedLabel : `Show ${collapsedLabel.replace(/^\+/, "")}`}
      >
        <CaretIcon size={12} className={`${styles.bucketChev} ${expanded ? styles.bucketChevOpen : ""}`} />
        <span className={styles.bucketLabel}>{expanded ? expandedLabel : collapsedLabel}</span>
        {failed > 0 && (
          <span className={styles.bucketFailed}>
            <Icon name="triangle-alert" size={13} color="var(--c-danger)" />
            {failed} failed
          </span>
        )}
      </button>
      <Reveal open={expanded}>
        <div className={styles.bucketList}>
          {bucket.map(([t, i]) => step(t, i))}
        </div>
      </Reveal>
      {active && step(tools[runningIdx], runningIdx)}
    </div>
  );
});
