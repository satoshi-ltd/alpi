import { OverlayScope, useOverlay } from "../hooks/useOverlay.js";
import { useId, useRef } from "react";
import { createPortal } from "react-dom";

import IconBtn from "./IconBtn.jsx";
import Tip from "./Tip.jsx";
import { XIcon } from "./icons.jsx";
import styles from "./Modal.module.css";

export default function Modal({
  open,
  onClose,
  title,
  "aria-label": ariaLabel,
  width,
  closeOnBackdrop = true,
  closeButton = false,
  children,
}) {
  const wrapRef = useRef(null);
  const controlled = open !== undefined;
  const visible = !controlled || open;

  const titleId = useId();
  const isTop = useOverlay({ open: visible, onClose, ref: wrapRef, modal: true });

  if (!visible) return null;

  const body = (
    <div
      className={`anim-overlay ${styles.backdrop}`}
      onMouseDown={(e) => {
        if (isTop() && closeOnBackdrop && e.target === e.currentTarget) onClose?.();
      }}
    >
      <div
        ref={wrapRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        aria-label={ariaLabel}
        tabIndex={-1}
        className={`anim-dialog ${styles.modal}`}
        style={width ? { "--dialog-width": typeof width === "number" ? `${width}px` : width } : undefined}
      >
        {(title || closeButton) && (
          <div className={styles.titleRow}>
            {title && <div id={titleId} className={styles.title}>{title}</div>}
            {closeButton && (
              <Tip text="Close" side="down">
                <IconBtn
                  aria-label="Close"
                  className={styles.closeBtn}
                  onClick={() => onClose?.()}
                >
                  <XIcon />
                </IconBtn>
              </Tip>
            )}
          </div>
        )}
        <div className={styles.content}>{children}</div>
      </div>
    </div>
  );

  return createPortal(<OverlayScope overlay={isTop}>{body}</OverlayScope>, document.body);
}
