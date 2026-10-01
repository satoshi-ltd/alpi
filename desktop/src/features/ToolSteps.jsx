import { memo, useCallback, useEffect, useState } from "react";

import CodeView from "../primitives/CodeView.jsx";
import IconBtn from "../primitives/IconBtn.jsx";
import Reasoning from "../primitives/Reasoning.jsx";
import Reveal from "../primitives/Reveal.jsx";
import Tip from "../primitives/Tip.jsx";
import { CaretIcon, CopyIcon, Icon } from "../primitives/icons.jsx";
import { useNotify } from "../primitives/Notification.jsx";
import { pluralize } from "../../../common/pluralize.mjs";
import { copyText } from "../lib/clipboard.js";
import { fmtToolDuration, prettyArgs, toolIcon, toolResult, toolSummary } from "../lib/toolSteps.js";
import styles from "./ToolSteps.module.css";
import { EMPTY } from "../../../common/emptyCopy.mjs";

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
            <div className={styles.empty}>{status === "running" ? "Running…" : EMPTY.toolOutput.title}</div>
          )}
        </div>
      </Reveal>
    </div>
  );
});

export const ProcessBlock = memo(function ProcessBlock({ entries, accent, thinking = false, answered = false }) {
  const [bucketChoice, setBucketChoice] = useState(null);
  const [overrides, setOverrides] = useState({});
  const setStep = useCallback((key, value) => setOverrides((prev) => ({ ...prev, [key]: value })), []);
  const base = Array.isArray(entries) ? entries : [];
  const list = thinking && !base[base.length - 1]?.tail
    ? [...base, { kind: "reasoning", key: `r${base.filter((e) => e.kind === "reasoning").length}`, text: "", tail: true }]
    : base;
  if (!list.length) return null;
  const isOpen = (e) => overrides[e.key] ?? toolStatus(e.tool) === "fail";
  const row = (e) => (e.kind === "tool" ? (
    <ToolStep
      key={e.key}
      tool={e.tool}
      accent={accent}
      open={isOpen(e)}
      onToggle={(value) => setStep(e.key, value)}
    />
  ) : (
    <Reasoning
      key={e.key}
      text={e.text}
      seconds={e.seconds}
      timeline={e.timeline}
      streaming={thinking && !!e.tail}
      answered={answered}
    />
  ));

  const toolAt = list.flatMap((e, i) => (e.kind === "tool" ? [i] : []));
  if (toolAt.length < 2) {
    return <div className={styles.module}>{list.map(row)}</div>;
  }

  const first = toolAt[0];
  const last = toolAt[toolAt.length - 1];
  const runningAt = toolAt.find((i) => list[i].tool.ok == null);
  const active = runningAt !== undefined;
  const live = new Set();
  if (active) {
    live.add(runningAt);
    if (runningAt - 1 > first && list[runningAt - 1].kind === "reasoning") live.add(runningAt - 1);
  }
  const bucket = [];
  for (let i = first; i <= last; i += 1) if (!live.has(i)) bucket.push(list[i]);
  const bucketTools = bucket.filter((e) => e.kind === "tool");
  const n = bucketTools.length;
  const noun = pluralize(n, "tool call");
  const failed = bucketTools.filter((e) => toolStatus(e.tool) === "fail").length;
  const expanded = bucketChoice ?? bucketTools.some(isOpen);
  const thoughts = bucket.filter((e) => e.kind === "reasoning").length;
  const thoughtNote = thoughts ? ` · ${thoughts} ${pluralize(thoughts, "thought")}` : "";
  const collapsedLabel = `${active ? `+${n} previous ${noun}` : `${n} ${noun}`}${thoughtNote}`;
  const expandedLabel = active ? "Hide previous tool calls" : "Hide tool calls";
  return (
    <div className={styles.module}>
      {list.slice(0, first).map(row)}
      <div className={styles.group}>
        <button
          type="button"
          className={styles.bucket}
          onClick={() => setBucketChoice(!expanded)}
          aria-expanded={expanded}
          aria-label={expanded ? expandedLabel : `Show ${collapsedLabel.replace(/^\+/, "")}`}
        >
          <CaretIcon size={14} className={`${styles.bucketChev} ${expanded ? styles.bucketChevOpen : ""}`} />
          <span className={styles.bucketLabel}>{expanded ? expandedLabel : collapsedLabel}</span>
          {failed > 0 && (
            <span className={styles.bucketFailed}>
              <Icon name="triangle-alert" size={12} color="var(--c-danger)" />
              {failed} failed
            </span>
          )}
        </button>
        <Reveal open={expanded} className={styles.bucketReveal}>
          <div className={styles.bucketList}>{bucket.map(row)}</div>
        </Reveal>
      </div>
      {[...live].sort((a, b) => a - b).map((i) => row(list[i]))}
      {list.slice(last + 1).map(row)}
    </div>
  );
});
