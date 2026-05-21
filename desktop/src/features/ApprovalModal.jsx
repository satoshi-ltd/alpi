import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

import { Modal } from "../primitives/index.js";
import styles from "./ApprovalModal.module.css";

const CHOICES = [
  { value: "once", label: "Allow once", hint: "Approve just this command." },
  { value: "session", label: "Allow this session", hint: "Re-approve next time the daemon restarts." },
  { value: "always", label: "Always allow this pattern", hint: "Persist in config.yaml allowlist." },
  { value: "deny", label: "Deny", hint: "Refuse — model will be told and move on.", danger: true },
];

// Hooks into App.jsx's daemon-event stream via the `requests` prop (a queue of pending approvals).
// Top of queue is shown; on respond/dismiss it pops. respond() calls host.approval.respond through Rust.
export default function ApprovalModal({ requests, onResolved }) {
  const current = requests[0] ?? null;
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  // 1Hz tick so `auto-deny in Ns` actually counts down between renders.
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    setBusy(false);
    setErr(null);
  }, [current?.request_id]);

  useEffect(() => {
    if (!current?.deadline) return undefined;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [current?.deadline]);

  const remaining = current?.deadline
    ? Math.max(0, Math.round((current.deadline - now) / 1000))
    : null;

  if (!current) return null;

  async function choose(choice) {
    if (busy) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await invoke("approval_respond", {
        requestId: current.request_id,
        choice,
      });
      // Daemon returns {ok: false, reason} when the request expired racing the timeout — surface it but still pop locally.
      if (res && res.ok === false) {
        setErr(res.reason || "request no longer pending");
      }
      onResolved?.(current.request_id, choice);
    } catch (e) {
      setErr(String(e?.message || e));
      setBusy(false);
    }
  }

  return (
    <Modal open closeOnBackdrop={false} width={480}>
      <div className={styles.head}>
        <div className={styles.severity}>
          <span className={styles.dot} data-severity={current.severity} />
          {(current.severity || "caution").toUpperCase()}
        </div>
        <div className={styles.pattern}>{current.pattern}</div>
      </div>
      <pre className={styles.command}>{current.command}</pre>
      {current.profile ? (
        <div className={styles.meta}>profile: {current.profile}</div>
      ) : null}
      {remaining !== null ? (
        <div className={styles.meta}>auto-deny in {remaining}s</div>
      ) : null}
      <div className={styles.choices}>
        {CHOICES.map((c) => (
          <button
            key={c.value}
            type="button"
            className={`${styles.choice} ${c.danger ? styles.danger : ""}`}
            onClick={() => choose(c.value)}
            disabled={busy}
          >
            <div className={styles.choiceLabel}>{c.label}</div>
            <div className={styles.choiceHint}>{c.hint}</div>
          </button>
        ))}
      </div>
      {err ? <div className={styles.error}>{err}</div> : null}
    </Modal>
  );
}
