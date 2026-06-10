import { useEffect, useRef, useState } from "react";
import Button from "../../../primitives/Button.jsx";
import Eyebrow from "../../../primitives/Eyebrow.jsx";
import Field from "../../../primitives/Field.jsx";
import useAutoPosition from "../../../primitives/useAutoPosition.js";
import { useDismissOnOutside } from "../../../hooks/useDismissOnOutside.js";
import styles from "../Settings.module.css";

export function BudgetEditor({ current, onSave }) {
  const [open, setOpen] = useState(false);
  const anchorRef = useRef(null);
  const popoverRef = useRef(null);
  const wrapRef = useRef(null);
  const [value, setValue] = useState(current != null ? String(current) : "");
  const [saving, setSaving] = useState(false);
  const pos = useAutoPosition({
    open,
    anchorRef,
    popoverRef,
    direction: "down",
    align: "left",
  });

  useEffect(() => {
    if (open) setValue(current != null ? String(current) : "");
  }, [open, current]);

  useDismissOnOutside({ open, onClose: () => setOpen(false), wrapRef });

  const trimmed = value.trim();
  const parsed = trimmed === "" ? null : Number(trimmed);
  const valid = trimmed === "" || (Number.isFinite(parsed) && parsed > 0);
  const dirty = valid && (parsed ?? null) !== (current ?? null);

  async function save() {
    if (!valid || !dirty || saving) return;
    setSaving(true);
    try {
      await onSave?.(parsed);
      setOpen(false);
    } catch {
    } finally {
      setSaving(false);
    }
  }

  return (
    <span ref={wrapRef} className={styles.popoverAnchor}>
      <span ref={anchorRef}>
        <Button size="sm" onClick={() => setOpen((o) => !o)}>
          {current != null ? "Edit" : "Set cap"}
        </Button>
      </span>
      {open && (
        <div
          ref={popoverRef}
          className={`${pos.ready ? "anim-pop " : ""}${styles.popover}`}
          style={{
            minWidth: 260,
            maxWidth: pos.maxWidth ?? undefined,
            position: "fixed",
            top: pos.top,
            left: pos.left,
            right: "auto",
            bottom: "auto",
            visibility: pos.ready ? "visible" : "hidden",
          }}
        >
          <div className={styles.field}>
            <Eyebrow as="label">USD lifetime cap</Eyebrow>
            <Field
              className={styles.input}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="empty = unlimited"
              spellCheck={false}
              autoFocus
            />
          </div>
          {!valid && <div className={styles.warn}>must be a positive number</div>}
          <div className={styles.actions}>
            <Button
              size="sm"
              variant="primary"
              onClick={save}
              disabled={!valid || !dirty}
              loading={saving}
            >
              Save
            </Button>
          </div>
        </div>
      )}
    </span>
  );
}
