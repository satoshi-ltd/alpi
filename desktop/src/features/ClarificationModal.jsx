import { useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

import { Button, DialogFooter, Eyebrow, IconBtn, Modal, Textarea, Tip } from "../primitives/index.js";
import { CheckIcon, EditIcon, XIcon } from "../primitives/icons.jsx";
import styles from "./ClarificationModal.module.css";
import { isComposing } from "../lib/composition.js";

function modeFor(current) {
  if (!current) return "single";
  if (current.multi) return "multi";
  if (!current.allow_other && current.choices?.length === 2) return "confirm";
  return "single";
}

export default function ClarificationModal({ requests, onResolved }) {
  const current = requests[0] ?? null;
  const mode = modeFor(current);

  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [otherText, setOtherText] = useState("");
  const [otherMode, setOtherMode] = useState(false);
  const [picked, setPicked] = useState([]);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    setBusy(false);
    setErr(null);
    setOtherText("");
    setOtherMode(false);
    setPicked([]);
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
    if (!current) return "";
    const tail = remaining !== null ? `auto-cancel in ${remaining}s` : null;
    return ["Question", tail].filter(Boolean).join(" · ");
  }, [current, remaining]);

  if (!current) return null;

  async function respond(choice) {
    if (busy) return;
    const text = (choice || "").trim();
    if (!text) {
      setErr("answer cannot be empty");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const res = await invoke("clarification_respond", {
        requestId: current.request_id,
        choice: text,
      });
      // Server-side validation can reject; keep the request and surface the reason so the user can retry.
      if (res && res.ok === false) {
        setErr(res.reason || "request no longer pending");
        setBusy(false);
        return;
      }
      onResolved?.(current.request_id, text);
    } catch (e) {
      setErr(String(e?.message || e));
      setBusy(false);
    }
  }

  function cancel() {
    respond("User cancelled clarification.");
  }

  function togglePick(label) {
    setPicked((prev) => (prev.includes(label) ? prev.filter((p) => p !== label) : [...prev, label]));
  }

  return (
    <Modal open onClose={busy ? undefined : cancel} closeOnBackdrop={false} width="var(--modal-md)" aria-label={current.question}>
      <div className={styles.head}>
        <div className={styles.headText}>
          <Eyebrow>{eyebrow}</Eyebrow>
          <div className={styles.question}>{current.question}</div>
        </div>
        <Tip text="Close" side="down">
          <IconBtn aria-label="Close" onClick={cancel} disabled={busy}>
            <XIcon />
          </IconBtn>
        </Tip>
      </div>

      {mode === "multi" ? (
        <MultiBody choices={current.choices} picked={picked} onToggle={togglePick} busy={busy} />
      ) : mode === "confirm" ? null : (
        <SingleBody
          choices={current.choices}
          allowOther={current.allow_other}
          otherMode={otherMode}
          setOtherMode={setOtherMode}
          otherText={otherText}
          setOtherText={setOtherText}
          onPick={respond}
          busy={busy}
        />
      )}

      {err ? <div className={styles.error}>{err}</div> : null}

      {mode === "multi" ? (
        <DialogFooter
          primaryLabel={picked.length > 0 ? `Continue · ${picked.length}` : "Continue"}
          primaryDisabled={picked.length === 0}
          primaryLoading={busy}
          onPrimary={() => respond(JSON.stringify(picked))}
        />
      ) : mode === "confirm" ? (
        <DialogFooter
          onCancel={() => respond(current.choices[1].label)}
          cancelLabel={current.choices[1].label}
          primaryLabel={current.choices[0].label}
          primaryLoading={busy}
          onPrimary={() => respond(current.choices[0].label)}
        />
      ) : null}
    </Modal>
  );
}

function SingleBody({
  choices,
  allowOther,
  otherMode,
  setOtherMode,
  otherText,
  setOtherText,
  onPick,
  busy,
}) {
  return (
    <div className={styles.choices}>
      {choices.map((c) => (
        <button
          key={c.label}
          type="button"
          className={styles.row}
          onClick={() => onPick(c.label)}
          disabled={busy || otherMode}
        >
          <span className={styles.radio} />
          <span className={styles.rowLabel}>{c.label}</span>
        </button>
      ))}
      {allowOther && !otherMode ? (
        <button
          type="button"
          className={`${styles.row} ${styles.rowOther}`}
          onClick={() => setOtherMode(true)}
          disabled={busy}
        >
          <span className={styles.rowIcon}><EditIcon size={16} /></span>
          <span className={styles.rowLabelMuted}>Type your own…</span>
        </button>
      ) : null}
      {allowOther && otherMode ? (
        <div className={styles.otherBlock}>
          <Textarea
            value={otherText}
            onChange={(e) => setOtherText(e.target.value)}
            placeholder="Type your answer…"
            autoFocus
            rows={3}
            className={styles.otherInput}
            disabled={busy}
            onKeyDown={(e) => {
              if (isComposing(e)) return;
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onPick(otherText);
              }
              if (e.key === "Escape") {
                e.preventDefault();
                e.stopPropagation();
                setOtherMode(false);
                setOtherText("");
              }
            }}
          />
          <div className={styles.otherActions}>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => { setOtherMode(false); setOtherText(""); }}
              disabled={busy}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => onPick(otherText)}
              disabled={busy || !otherText.trim()}
            >
              Send
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function MultiBody({ choices, picked, onToggle, busy }) {
  return (
    <div className={styles.choices}>
      {choices.map((c) => {
        const checked = picked.includes(c.label);
        return (
          <button
            key={c.label}
            type="button"
            className={`${styles.row} ${checked ? styles.rowChecked : ""}`}
            onClick={() => onToggle(c.label)}
            disabled={busy}
          >
            <span className={`${styles.checkbox} ${checked ? styles.checkboxChecked : ""}`}>
              {checked ? <CheckIcon size={14} /> : null}
            </span>
            <span className={styles.rowLabel}>{c.label}</span>
          </button>
        );
      })}
    </div>
  );
}
