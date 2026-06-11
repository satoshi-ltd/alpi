import { useState, useEffect } from "react";
import Popover from "./Popover.jsx";
import DialogFooter from "./DialogFooter.jsx";
import { Field, Selectish, Eyebrow } from "./index.js";
import styles from "./BudgetEdit.module.css";

export default function BudgetEdit({ value, triggerLabel, onSave }) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(value ?? "");
  useEffect(() => {
    setDraft(value ?? "");
  }, [value, open]);

  const trimmed = String(draft).trim();
  const isEmpty = trimmed === "";
  const n = Number(trimmed);
  // empty clears the cap (unlimited) — an explicit value must be > 0
  const valid = isEmpty || (Number.isFinite(n) && n > 0);

  return (
    <span className={styles.root}>
      <Selectish onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        {triggerLabel ?? `$${Number(value || 0).toFixed(2)}/day`}
      </Selectish>
      <Popover open={open} onClose={() => setOpen(false)} width="var(--pop-sm)">
        <div className={styles.body}>
          <div className={styles.field}>
            <Eyebrow>Daily USD cap</Eyebrow>
            <Field
              mono
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="empty = unlimited"
              autoFocus
            />
          </div>
          <DialogFooter
            onCancel={() => setOpen(false)}
            primaryLabel="Save"
            primaryDisabled={!valid}
            onPrimary={() => {
              if (!valid) return;
              onSave?.({ mode: "usd", value: isEmpty ? "" : n });
              setOpen(false);
            }}
          />
        </div>
      </Popover>
    </span>
  );
}
