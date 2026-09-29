import { useEffect, useState } from "react";
import Popover from "./Popover.jsx";
import DialogFooter from "./DialogFooter.jsx";
import { Field, Selectish, Eyebrow } from "./index.js";
import styles from "./BudgetEdit.module.css";

export function parseBudget(text) {
  const trimmed = String(text ?? "").trim();
  if (trimmed === "") return { valid: true, next: null };
  const n = Number(trimmed);
  return Number.isFinite(n) && n > 0 ? { valid: true, next: n } : { valid: false, next: null };
}

export default function BudgetEdit({ value, label = "Daily USD cap", triggerLabel, align = "left", onSave }) {
  const current = value === "" || value == null ? null : Number(value);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (open) setDraft(current != null ? String(current) : "");
  }, [current, open]);

  const { valid, next } = parseBudget(draft);
  const dirty = valid && next !== current;

  async function save() {
    if (!dirty || saving) return;
    setSaving(true);
    try {
      await onSave?.(next);
      setOpen(false);
    } catch {
    } finally {
      setSaving(false);
    }
  }

  return (
    <span className={styles.root}>
      <Selectish onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        {triggerLabel ?? (current != null ? `$${current.toFixed(2)}` : "unlimited")}
      </Selectish>
      <Popover open={open} onClose={() => setOpen(false)} width="var(--pop-sm)" align={align}>
        <div className={styles.body}>
          <div className={styles.field}>
            <Eyebrow as="label">{label}</Eyebrow>
            <Field
              mono
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") save(); }}
              placeholder="empty = unlimited"
              aria-invalid={!valid}
              spellCheck={false}
              autoFocus
            />
            {!valid && <span className={styles.error}>Enter a positive number, or leave it empty for no cap</span>}
          </div>
          <DialogFooter
            onCancel={() => setOpen(false)}
            primaryLabel="Save"
            primaryDisabled={!dirty}
            primaryLoading={saving}
            onPrimary={save}
          />
        </div>
      </Popover>
    </span>
  );
}
