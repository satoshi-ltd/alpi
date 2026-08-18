import { useEffect, useMemo, useState } from "react";
import { profileLabel } from "../lib/profile-display.js";
import { invoke } from "@tauri-apps/api/core";

import { Button, Diamond, IconBtn, Modal, Tip } from "../primitives/index.js";
import { XIcon } from "../primitives/icons.jsx";
import styles from "./ApprovalModal.module.css";

const ALLOW_CHOICES = [
  { value: "once",    label: "Allow once",        hint: "just this invocation" },
  { value: "session", label: "Allow this session", hint: "remember until daemon restarts" },
  { value: "always",  label: "Always allow",       hint: "add to allowlist" },
];

// Closing the modal maps to "deny" — the safe default for an unattended caution/dangerous command.
export default function ApprovalModal({ requests, onResolved }) {
  const current = requests[0] ?? null;
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
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

  const eyebrow = useMemo(() => {
    if (!current) return null;
    const severity = (current.severity || "caution").toLowerCase();
    const tail = remaining !== null ? `AUTO-DENY IN ${remaining}S` : null;
    return { severity, sevLabel: severity.toUpperCase(), tail };
  }, [current, remaining]);

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
      if (res && res.ok === false) {
        setErr(res.reason || "request no longer pending");
      }
      onResolved?.(current.request_id, choice);
    } catch (e) {
      setErr(String(e?.message || e));
      setBusy(false);
    }
  }

  const deny = () => choose("deny");

  return (
    <Modal open closeOnBackdrop={false} width="var(--modal-md)">
      <div className={styles.head}>
        <div className={styles.headText}>
          <div className={styles.eyebrow}>
            <span className={styles.alertLabel}>ALERT</span>
            <span className={styles.sep}> · </span>
            <span className={styles.diamondWrap}>
              <Diamond color={`var(--c-danger)`} />
            </span>
            {current.profile ? (
              <span className={styles.profile}>@{profileLabel(current.profile).toUpperCase()}</span>
            ) : null}
            <span className={styles.sep}> · </span>
            <span className={styles.surface}>SHELL</span>
            {eyebrow.tail ? (
              <>
                <span className={styles.sep}> · </span>
                <span>{eyebrow.tail}</span>
              </>
            ) : null}
          </div>
          <div className={styles.title}>Allow this command?</div>
        </div>
        <Tip text="Close" side="down">
          <IconBtn aria-label="Close" onClick={deny} disabled={busy}>
            <XIcon />
          </IconBtn>
        </Tip>
      </div>

      <pre className={styles.command}>{current.command}</pre>
      {current.cwd ? <div className={styles.cwd}>cwd <span className={styles.cwdPath}>{current.cwd}</span></div> : null}

      <div className={styles.choices}>
        {ALLOW_CHOICES.map((c) => (
          <button
            key={c.value}
            type="button"
            className={styles.row}
            onClick={() => choose(c.value)}
            disabled={busy}
          >
            <div className={styles.rowLabel}>{c.label}</div>
            <div className={styles.rowHint}>{c.hint}</div>
          </button>
        ))}
      </div>

      <div className={styles.footer}>
        <Button
          variant="danger"
          size="lg"
          className={styles.denyBtn}
          onClick={deny}
          disabled={busy}
        >
          Deny
        </Button>
      </div>

      {err ? <div className={styles.error}>{err}</div> : null}
    </Modal>
  );
}
