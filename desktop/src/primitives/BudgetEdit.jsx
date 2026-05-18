import { useState, useEffect } from "react";
import Popover from "./Popover.jsx";
import DialogFooter from "./DialogFooter.jsx";
import { Field, Selectish, Eyebrow } from "./index.js";
import styles from "./BudgetEdit.module.css";

export default function BudgetEdit({
  value,
  mode = "usd",
  usdOnly = false,
  triggerLabel,
  onSave,
}) {
  const [open, setOpen] = useState(false);
  const [draftMode, setDraftMode] = useState(mode);
  const [draft, setDraft] = useState(value ?? "");
  useEffect(() => {
    setDraftMode(mode);
    setDraft(value ?? "");
  }, [value, mode, open]);

  return (
    <span className={styles.root}>
      <Selectish onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        {triggerLabel ??
          (mode === "usd"
            ? `$${Number(value || 0).toFixed(2)}/day`
            : `${value || 0} tokens/day`)}
      </Selectish>
      <Popover open={open} onClose={() => setOpen(false)} width="var(--pop-sm)">
        <div className={styles.body}>
          {!usdOnly && (
            <div className={styles.toggleRow}>
              {["usd", "tokens"].map((k) => (
                <button
                  key={k}
                  type="button"
                  onClick={() => setDraftMode(k)}
                  className={`ds-pill ${styles.togglePill} ${draftMode === k ? "is-on" : ""}`.trim()}
                >
                  {k}
                </button>
              ))}
            </div>
          )}
          <div className={styles.field}>
            <Eyebrow>
              {draftMode === "usd" ? "Daily USD cap" : "Daily tokens cap"}
            </Eyebrow>
            <Field
              mono
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder={draftMode === "usd" ? "2.00" : "100000"}
              autoFocus
            />
          </div>
          <DialogFooter
            onCancel={() => setOpen(false)}
            primaryLabel="Save"
            primaryDisabled={(() => {
              const n = Number(draft);
              return !Number.isFinite(n) || n < 0;
            })()}
            onPrimary={() => {
              const n = Number(draft);
              if (!Number.isFinite(n) || n < 0) return;
              onSave?.({ mode: draftMode, value: n });
              setOpen(false);
            }}
          />
        </div>
      </Popover>
    </span>
  );
}
