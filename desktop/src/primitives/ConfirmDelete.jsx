import Button from "./Button.jsx";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { useInsideOverlay, useOverlay } from "../hooks/useOverlay.js";
import Modal from "./Modal.jsx";
import Popover from "./Popover.jsx";
import DialogFooter from "./DialogFooter.jsx";
import { Field } from "./index.js";
import styles from "./ConfirmDelete.module.css";

const SheetHost = createContext(null);

export function ConfirmSheet({ children, flush = false, inset = "0px" }) {
  const [request, setRequest] = useState(null);
  const ref = useRef(null);
  const close = useCallback(() => setRequest(null), []);
  useOverlay({ open: !!request, onClose: close, ref, modal: true });
  return (
    <SheetHost.Provider value={setRequest}>
      <div className={styles.hostContent} style={{ display: request ? "none" : "contents" }}>{children}</div>
      {request && (
        <div ref={ref} className={styles.hostContent}>
          <ConfirmBody {...request} inModal={flush} inSheet={!flush} inset={inset} onClose={close} />
        </div>
      )}
    </SheetHost.Provider>
  );
}

function ConfirmBody({
  onClose,
  onConfirm,
  title,
  consequence,
  confirmLabel = "Delete",
  cancelLabel = "Cancel",
  typeToConfirm,
  inModal = false,
  inSheet = false,
  inset = "0px",
}) {
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const needsTyping = !!typeToConfirm;
  const armed = needsTyping ? typed === typeToConfirm : true;

  async function confirm() {
    if (!armed || busy) return;
    const result = onConfirm?.();
    if (result && typeof result.then === "function") {
      setBusy(true);
      try {
        await result;
      } catch {
        setBusy(false);
        return;
      }
    }
    onClose?.();
  }

  return (
    <div className={`${styles.body} ${inModal ? styles.inModal : ""} ${inSheet ? styles.inSheet : ""}`} role={inSheet || inModal ? "group" : undefined} aria-label={title} style={inSheet ? { "--sheet-inset": inset } : undefined}>
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
            onKeyDown={(e) => {
              if (e.key === "Enter") confirm();
            }}
            autoFocus
          />
        </div>
      )}
      <DialogFooter
        onCancel={onClose}
        cancelLabel={cancelLabel}
        primaryLabel={confirmLabel}
        primaryDisabled={!armed}
        primaryLoading={busy}
        destructive
        onPrimary={confirm}
      />
    </div>
  );
}

export default function ConfirmDelete({ open, onClose, anchored = true, width, ...request }) {
  const [round, setRound] = useState(0);
  useEffect(() => {
    if (!open) setRound((r) => r + 1);
  }, [open]);
  const insideOverlay = useInsideOverlay();
  const asModal = !anchored || !!request.typeToConfirm || insideOverlay;
  const resolvedWidth = width ?? (asModal ? "var(--pop-xl)" : "var(--pop-md)");
  const body = <ConfirmBody key={round} {...request} onClose={onClose} inModal={asModal} />;

  if (asModal) {
    return (
      <Modal open={open} onClose={onClose} width={resolvedWidth} aria-label={request.title}>
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
  const host = useContext(SheetHost);
  const Trigger = triggerVariant === "ghost" ? Button : "button";
  const request = { title, consequence, typeToConfirm, confirmLabel, cancelLabel, onConfirm };
  const triggerClass =
    triggerVariant === "ghost"
      ? styles.triggerGhost
      : "alink danger";
  return (
    <span className={styles.trigger}>
      <Trigger
        type="button"
        className={triggerClass}
        onClick={() => (host ? host(request) : setOpen(true))}
        disabled={disabled || loading}
      >
        {loading ? "Working…" : label}
      </Trigger>
      {!host && <ConfirmDelete
        anchored={anchored}
        open={open}
        onClose={() => setOpen(false)}
        onConfirm={onConfirm}
        title={title}
        consequence={consequence}
        typeToConfirm={typeToConfirm}
        confirmLabel={confirmLabel}
        cancelLabel={cancelLabel}
      />}
    </span>
  );
}
