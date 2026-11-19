import { memo, useEffect, useRef, useState } from "react";

import CodeView from "../primitives/CodeView.jsx";
import IconBtn from "../primitives/IconBtn.jsx";
import Reasoning from "../primitives/Reasoning.jsx";
import Reveal from "../primitives/Reveal.jsx";
import Tip from "../primitives/Tip.jsx";
import { CheckIcon, CopyIcon, Icon } from "../primitives/icons.jsx";
import { useNotify } from "../primitives/Notification.jsx";
import { pluralize } from "../../../common/pluralize.mjs";
import { workClock, workSummary } from "../../../common/workLine.mjs";
import Fold from "../primitives/Fold.jsx";
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

const COPIED_MS = 1500;

function CopyButton({ text, label }) {
  const notify = useNotify();
  const [copied, setCopied] = useState(false);
  const timer = useRef(null);
  useEffect(() => () => clearTimeout(timer.current), []);
  const onCopy = async (e) => {
    e.stopPropagation();
    if (await copyText(text)) {
      setCopied(true);
      clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), COPIED_MS);
    } else notify({ message: "Copy failed", variant: "error" });
  };
  const shown = copied ? "Copied" : label;
  return (
    <Tip text={shown} side="up-r" escape>
      <IconBtn aria-label={shown} onClick={onCopy} className={styles.copyBtn}>
        {copied ? <CheckIcon size="sm" /> : <CopyIcon size="sm" />}
      </IconBtn>
    </Tip>
  );
}

export const ToolStep = memo(function ToolStep({ tool, accent, open: openProp, onToggle }) {
  const status = toolStatus(tool);
  const [own, setOwn] = useState(null);
  const open = openProp ?? own ?? false;
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
  const iconColor = status === "fail" ? "var(--c-danger)" : status === "running" ? (accent || "var(--ink-2)") : "var(--ink-3)";
  const statusText = status === "fail"
    ? (dur ? `failed · ${dur}` : "failed")
    : status === "running" ? `${dur ? `${dur} ` : ""}…` : dur;

  return (
    <div className={`${styles.step} ${styles[`step_${status}`]}`} style={accent ? { "--c": accent } : undefined}>
      <button
        type="button"
        className={`${styles.head} ${open ? styles.headOpen : ""}`}
        onClick={toggle}
        aria-expanded={open}
        aria-label={`${tool.name}${summary ? ` ${summary}` : ""}`}
      >
        <Icon name={toolIcon(tool.name)} size={14} color={iconColor} className={styles.icon} />
        <span className={styles.name}>{tool.name}</span>
        <Icon name="chevron-right" size="sm" className={`${styles.chev} ${open ? styles.chevOpen : ""}`} />
        <span className={styles.summary}>{summary}</span>
        {statusText && <span className={`tnum ${styles.status}`}>{statusText}</span>}
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

function useWorkStart(running, earliest) {
  const start = useRef(null);
  if (running && start.current == null) start.current = Date.now();
  if (earliest != null && (start.current == null || earliest < start.current)) start.current = earliest;
  return start.current;
}

function useTicking(active) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return undefined;
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [active]);
  return now;
}

export function WorkClock({ begun }) {
  const now = useTicking(begun != null);
  const seconds = begun == null ? 0 : Math.floor(Math.max(0, now - begun) / 1000);
  const text = seconds >= 1 ? workClock(seconds) : "";
  return text ? <span className={styles.workClock}>{text}</span> : null;
}

function toolStart(tool) {
  const ms = startMs(tool);
  if (ms != null) return ms / 1000;
  return typeof tool.at === "number" && Number.isFinite(tool.at) ? tool.at : null;
}

const OPEN_LINES = new Map();
const OPEN_LINES_MAX = 200;

export function _resetOpenLines() {
  OPEN_LINES.clear();
}

function rememberOpen(key, value) {
  if (!key) return;
  OPEN_LINES.delete(key);
  OPEN_LINES.set(key, value);
  if (OPEN_LINES.size > OPEN_LINES_MAX) OPEN_LINES.delete(OPEN_LINES.keys().next().value);
}

export const ProcessBlock = memo(function ProcessBlock({ entries, accent, shape, thinking = false, answered = false, running = false, writing = false, note = "", memoryKey = null }) {
  const keys = memoryKey == null ? [] : Array.isArray(memoryKey) ? memoryKey : [memoryKey];
  const [open, setOpenState] = useState(() => keys.map((k) => OPEN_LINES.get(k)).find((v) => v != null) ?? false);
  const setOpen = (value) => {
    setOpenState(value);
    rememberOpen(keys[0], value);
  };
  const adoptFrom = keys.length > 1 ? keys[1] : null;
  useEffect(() => {
    if (!adoptFrom || !OPEN_LINES.has(adoptFrom)) return;
    if (!OPEN_LINES.has(keys[0])) rememberOpen(keys[0], OPEN_LINES.get(adoptFrom));
    OPEN_LINES.delete(adoptFrom);
  }, [adoptFrom]);
  const [overrides, setOverrides] = useState({});
  const toggles = useRef(new Map());
  const toggleFor = (key) => {
    if (!toggles.current.has(key)) toggles.current.set(key, (value) => setOverrides((prev) => ({ ...prev, [key]: value })));
    return toggles.current.get(key);
  };
  const base = Array.isArray(entries) ? entries : [];
  const list = thinking && !base[base.length - 1]?.tail
    ? [...base, { kind: "reasoning", key: `r${base.filter((e) => e.kind === "reasoning").length}`, text: "", tail: true }]
    : base;
  const summary = workSummary(list.map((e) => (e.kind === "tool"
    ? { kind: "tool", name: e.tool.name, target: toolSummary(e.tool), ok: e.tool.ok, seconds: e.tool.duration_s, start: toolStart(e.tool) ?? undefined }
    : { kind: "thought", text: e.text, seconds: e.seconds, live: thinking && !!e.tail && !note })), { thinking, running, writing, note });
  const starts = list.filter((e) => e.kind === "tool").map((e) => startMs(e.tool)).filter((v) => v != null);
  const begun = useWorkStart(summary.running, starts.length ? Math.min(...starts) : null);
  if (!list.length) return null;

  const clock = summary.running ? "" : workClock(summary.seconds);
  const row = (e) => (e.kind === "tool" ? (
    <ToolStep
      key={e.key}
      tool={e.tool}
      accent={accent}
      open={overrides[e.key] ?? false}
      onToggle={toggleFor(e.key)}
    />
  ) : (
    <Reasoning
      key={e.key}
      accent={accent}
      shape={shape}
      text={e.text}
      seconds={e.seconds}
      timeline={e.timeline}
      streaming={thinking && !!e.tail}
      answered={answered}
    />
  ));
  const stepsText = `${summary.steps} ${pluralize(summary.steps, "step")}`;
  const lead = summary.running ? "Working" : clock ? `Worked for ${clock}` : "Worked";
  const label = summary.running
    ? `Working · ${summary.phrase}`
    : `${lead} · ${stepsText}${summary.failed ? ` · ${summary.failed} failed` : ""}`;
  return (
    <div className={styles.module} style={accent ? { "--c": accent } : undefined}>
      <button
        type="button"
        className={styles.workLine}
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-label={label}
        data-work-state={summary.running ? "running" : "done"}
      >
        <Fold shape={shape} color={accent} size="row" state={summary.running ? "working" : "idle"} />
        <span className={styles.workLead}>{lead}</span>
        {summary.running ? (
          <span className={styles.workDetail}>{summary.phrase}…</span>
        ) : (
          <>
            <span className={styles.workDetail}>· {stepsText}</span>
            {summary.failed > 0 && (
              <span className={styles.workFailed}>
                <Icon name="triangle-alert" size="sm" color="var(--c-danger)" />
                {summary.failed} failed
              </span>
            )}
          </>
        )}
        <Icon name="chevron-right" size="sm" className={`${styles.bucketChev} ${open ? styles.bucketChevOpen : ""}`} />
        {summary.running && <WorkClock begun={begun} />}
      </button>
      <span className={styles.srOnly} role="status" aria-live="polite">{summary.running ? summary.phrase : label}</span>
      <Reveal open={open} className={styles.workReveal}>
        <div className={styles.workRail}>{list.map(row)}</div>
      </Reveal>
    </div>
  );
});
