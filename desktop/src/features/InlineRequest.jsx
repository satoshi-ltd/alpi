import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

import Button from "../primitives/Button.jsx";
import Textarea from "../primitives/Textarea.jsx";
import { Icon } from "../primitives/icons.jsx";
import { profileLabel } from "../lib/profile-display.js";
import styles from "./InlineRequest.module.css";
import { isComposing } from "../lib/composition.js";

const CANCEL_CLARIFICATION = "User cancelled clarification.";

function useRemaining(deadline) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!deadline) return undefined;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [deadline]);
  return deadline ? Math.max(0, Math.round((deadline - now) / 1000)) : null;
}

function useResponder(command, request, onResolved, { keepOnReject }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  useEffect(() => {
    setBusy(false);
    setErr(null);
  }, [request?.request_id]);
  async function respond(choice) {
    if (busy) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await invoke(command, { requestId: request.request_id, choice });
      if (res && res.ok === false) {
        setErr(res.reason || "request no longer pending");
        if (keepOnReject) {
          setBusy(false);
          return;
        }
      }
      onResolved?.(request.request_id, choice);
    } catch (e) {
      setErr(String(e?.message || e));
      setBusy(false);
    }
  }
  return { busy, err, respond };
}

function escapeTo(action) {
  return (e) => {
    if (e.key !== "Escape" || e.defaultPrevented) return;
    e.preventDefault();
    e.stopPropagation();
    action();
  };
}

export function InlineApproval({ request, onResolved }) {
  const { busy, err, respond } = useResponder("approval_respond", request, onResolved, { keepOnReject: false });
  const remaining = useRemaining(request?.deadline);
  if (!request) return null;
  const severity = (request.severity || "caution").toLowerCase();
  const who = request.profile ? `@${profileLabel(request.profile)}` : "The agent";
  return (
    <div
      role="group"
      aria-label="Allow this command?"
      className={`${styles.card} ${severity === "dangerous" ? styles.dangerous : ""}`}
      onKeyDown={escapeTo(() => respond("deny"))}
    >
      <div className={styles.head}>
        <Icon name="triangle-alert" size={14} className={styles.alert} />
        <span className={styles.title}>{who} wants to run a command</span>
        {remaining !== null && <span className={`tnum ${styles.countdown}`}>auto-deny in {remaining}s</span>}
      </div>
      <pre className={styles.command}>{request.command}</pre>
      {request.cwd ? <div className={styles.cwd}>cwd {request.cwd}</div> : null}
      <div className={styles.actions}>
        <Button variant="secondary" size="sm" onClick={() => respond("deny")} disabled={busy}>Deny</Button>
        <Button variant="primary" size="sm" onClick={() => respond("once")} disabled={busy}>Allow once</Button>
        <Button variant="secondary" size="sm" onClick={() => respond("session")} disabled={busy}>Allow this session</Button>
        <Button variant="secondary" size="sm" onClick={() => respond("always")} disabled={busy}>Always allow</Button>
      </div>
      {err ? <div className={styles.error}>{err}</div> : null}
    </div>
  );
}

function modeFor(req) {
  if (req.multi) return "multi";
  if (!req.allow_other && req.choices?.length === 2) return "confirm";
  return "single";
}

export function InlineClarification({ request, onResolved }) {
  const { busy, err, respond } = useResponder("clarification_respond", request, onResolved, { keepOnReject: true });
  const remaining = useRemaining(request?.deadline);
  const [picked, setPicked] = useState([]);
  const [otherMode, setOtherMode] = useState(false);
  const [otherText, setOtherText] = useState("");
  useEffect(() => {
    setPicked([]);
    setOtherMode(false);
    setOtherText("");
  }, [request?.request_id]);
  if (!request) return null;
  const mode = modeFor(request);
  const choices = request.choices ?? [];
  const send = (text) => {
    const v = String(text || "").trim();
    if (v) respond(v);
  };
  const toggle = (label) => setPicked((prev) => (prev.includes(label) ? prev.filter((p) => p !== label) : [...prev, label]));

  return (
    <div
      role="group"
      aria-label={request.question}
      className={styles.card}
      onKeyDown={escapeTo(() => respond(CANCEL_CLARIFICATION))}
    >
      <div className={styles.head}>
        <Icon name="sparkle" size={14} className={styles.ask} />
        <span className={styles.title}>{request.question}</span>
        {remaining !== null && <span className={`tnum ${styles.countdown}`}>auto-cancel in {remaining}s</span>}
      </div>
      {mode === "confirm" ? (
        <div className={styles.actions}>
          <Button variant="secondary" size="sm" onClick={() => respond(choices[1].label)} disabled={busy}>{choices[1].label}</Button>
          <Button variant="primary" size="sm" onClick={() => respond(choices[0].label)} disabled={busy}>{choices[0].label}</Button>
        </div>
      ) : mode === "multi" ? (
        <>
          <div className={styles.choices}>
            {choices.map((c) => (
              <Button
                key={c.label}
                variant="secondary"
                size="sm"
                active={picked.includes(c.label)}
                aria-pressed={picked.includes(c.label)}
                onClick={() => toggle(c.label)}
                disabled={busy}
              >
                {c.label}
              </Button>
            ))}
          </div>
          <div className={styles.actions}>
            <Button variant="secondary" size="sm" onClick={() => respond(CANCEL_CLARIFICATION)} disabled={busy}>Skip</Button>
            <Button variant="primary" size="sm" onClick={() => respond(JSON.stringify(picked))} disabled={busy || picked.length === 0}>
              {picked.length > 0 ? `Continue · ${picked.length}` : "Continue"}
            </Button>
          </div>
        </>
      ) : (
        <>
          <div className={styles.choices}>
            {choices.map((c) => (
              <Button key={c.label} variant="secondary" size="sm" onClick={() => respond(c.label)} disabled={busy || otherMode} title={c.description || undefined}>
                {c.label}
              </Button>
            ))}
            {request.allow_other && !otherMode && (
              <Button variant="ghost" size="sm" onClick={() => setOtherMode(true)} disabled={busy}>Type your own…</Button>
            )}
          </div>
          {request.allow_other && otherMode && (
            <div className={styles.other}>
              <Textarea
                value={otherText}
                onChange={(e) => setOtherText(e.target.value)}
                placeholder="Type your answer…"
                autoFocus
                rows={2}
                disabled={busy}
                className={styles.otherInput}
                onKeyDown={(e) => {
                  if (isComposing(e)) return;
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send(otherText);
                  }
                  if (e.key === "Escape") {
                    e.preventDefault();
                    e.stopPropagation();
                    setOtherMode(false);
                    setOtherText("");
                  }
                }}
              />
              <Button variant="primary" size="sm" onClick={() => send(otherText)} disabled={busy || !otherText.trim()}>Send</Button>
            </div>
          )}
        </>
      )}
      {err ? <div className={styles.error}>{err}</div> : null}
    </div>
  );
}
