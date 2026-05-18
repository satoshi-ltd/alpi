import { useEffect, useState } from "react";
import Modal from "./Modal.jsx";
import Popover from "./Popover.jsx";
import DialogFooter from "./DialogFooter.jsx";
import { Field } from "./index.js";
import styles from "./ConfirmDelete.module.css";

export default function ConfirmDelete({
  mode = "simple",
  open,
  onClose,
  onConfirm,
  title,
  consequence,
  confirmLabel = "Delete",
  cancelLabel = "Cancel",
  typeToConfirm,
  anchored = true,
  width = mode === "typed" ? "var(--pop-xl)" : "var(--pop-md)",
}) {
  const [typed, setTyped] = useState("");
  useEffect(() => {
    if (!open) setTyped("");
  }, [open]);

  const isTyped = mode === "typed";
  const armed = isTyped ? typed === typeToConfirm : true;

  const body = (
    <div className={`${styles.body} ${isTyped ? styles.typed : ""}`}>
      <div className={styles.heading}>
        <div className={styles.title}>{title}</div>
        {consequence && <div className={styles.consequence}>{consequence}</div>}
      </div>
      {isTyped && typeToConfirm && (
        <div className={styles.typedBlock}>
          <div className={styles.typedHint}>
            <span className={styles.typedHintLabel}>Type</span>
            <span className={styles.typedToken}>{typeToConfirm}</span>
            <span className={styles.typedHintLabel}>to confirm</span>
          </div>
          <Field
            mono
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            autoFocus
          />
        </div>
      )}
      <DialogFooter
        onCancel={onClose}
        cancelLabel={cancelLabel}
        primaryLabel={confirmLabel}
        primaryDisabled={!armed}
        destructive
        onPrimary={() => {
          onConfirm?.();
          onClose?.();
        }}
      />
    </div>
  );

  if (isTyped) {
    return (
      <Modal open={open} onClose={onClose} width={width}>
        {body}
      </Modal>
    );
  }
  if (anchored) {
    return (
      <Popover open={open} onClose={onClose} width={width} align="right">
        {body}
      </Popover>
    );
  }
  return (
    <Modal open={open} onClose={onClose} width={width}>
      {body}
    </Modal>
  );
}

export function ConfirmDeleteAction({
  label,
  mode = "simple",
  title,
  consequence,
  typeToConfirm,
  confirmLabel,
  cancelLabel,
  onConfirm,
  disabled = false,
  loading = false,
  triggerVariant = "alink",
}) {
  const [open, setOpen] = useState(false);
  const triggerClass =
    triggerVariant === "ghost"
      ? `btn btn-ghost ${styles.triggerGhost}`
      : "alink danger";
  return (
    <span className={styles.trigger}>
      <button
        type="button"
        className={triggerClass}
        onClick={() => setOpen(true)}
        disabled={disabled || loading}
      >
        {loading ? "Working…" : label}
      </button>
      <ConfirmDelete
        mode={mode}
        open={open}
        onClose={() => setOpen(false)}
        onConfirm={onConfirm}
        title={title}
        consequence={consequence}
        typeToConfirm={typeToConfirm}
        confirmLabel={confirmLabel}
        cancelLabel={cancelLabel}
      />
    </span>
  );
}
