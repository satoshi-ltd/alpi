import { useEffect, useState } from "react";
import Modal from "./Modal.jsx";
import Popover from "./Popover.jsx";
import DialogFooter from "./DialogFooter.jsx";
import { Field } from "./index.js";
import styles from "./ConfirmDelete.module.css";

export default function ConfirmDelete({
  open,
  onClose,
  onConfirm,
  title,
  consequence,
  confirmLabel = "Delete",
  cancelLabel = "Cancel",
  typeToConfirm,
  anchored = true,
  width,
}) {
  const [typed, setTyped] = useState("");
  useEffect(() => {
    if (!open) setTyped("");
  }, [open]);

  const needsTyping = !!typeToConfirm;
  const asModal = !anchored || needsTyping;
  const armed = needsTyping ? typed === typeToConfirm : true;
  const resolvedWidth = width ?? (asModal ? "var(--pop-xl)" : "var(--pop-md)");

  const body = (
    <div className={`${styles.body} ${asModal ? styles.inModal : ""}`}>
      <div className={styles.heading}>
        <div className={styles.title}>{title}</div>
        {consequence && <div className={styles.consequence}>{consequence}</div>}
      </div>
      {needsTyping && (
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

  if (asModal) {
    return (
      <Modal open={open} onClose={onClose} width={resolvedWidth}>
        {body}
      </Modal>
    );
  }
  return (
    <Popover open={open} onClose={onClose} width={resolvedWidth} align="right">
      {body}
    </Popover>
  );
}

export function ConfirmDeleteAction({
  label,
  title,
  consequence,
  typeToConfirm,
  confirmLabel,
  cancelLabel,
  onConfirm,
  disabled = false,
  loading = false,
  triggerVariant = "alink",
  anchored = true,
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
        anchored={anchored}
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
