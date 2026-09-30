import { OverlayScope, useOverlay } from "../hooks/useOverlay.js";
import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import IconBtn from "./IconBtn.jsx";
import Tip from "./Tip.jsx";
import { XIcon } from "./icons.jsx";
import styles from "./Modal.module.css";

const EXIT_FALLBACK_MS = 160;

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

  const [shown, setShown] = useState(visible);
  if (visible && !shown) setShown(true);
  const closing = shown && !visible;
  const frozen = useRef({ title, children });
  if (visible) frozen.current = { title, children };

  useLayoutEffect(() => {
    if (closing && wrapRef.current?.contains(document.activeElement)) document.activeElement.blur();
  }, [closing]);

  useEffect(() => {
    if (!closing) return undefined;
    const t = setTimeout(() => setShown(false), EXIT_FALLBACK_MS);
    return () => clearTimeout(t);
  }, [closing]);

  if (!visible && !closing) return null;
  const shownTitle = closing ? frozen.current.title : title;
  const shownChildren = closing ? frozen.current.children : children;

  const body = (
    <div
      className={closing ? `${styles.backdrop} ${styles.backdropClosing}` : `anim-overlay ${styles.backdrop}`}
      data-closing={closing || undefined}
      aria-hidden={closing || undefined}
      onMouseDown={(e) => {
        if (closing) return;
        if (isTop() && closeOnBackdrop && e.target === e.currentTarget) onClose?.();
      }}
    >
      <div
        ref={wrapRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={shownTitle ? titleId : undefined}
        aria-label={ariaLabel}
        tabIndex={-1}
        className={closing ? `${styles.modal} ${styles.modalClosing}` : `anim-dialog ${styles.modal}`}
        onAnimationEnd={(e) => {
          if (closing && e.target === e.currentTarget) setShown(false);
        }}
        style={width ? { "--dialog-width": typeof width === "number" ? `${width}px` : width } : undefined}
      >
        {(shownTitle || closeButton) && (
          <div className={styles.titleRow}>
            {shownTitle && <div id={titleId} className={styles.title}>{shownTitle}</div>}
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
        <div className={styles.content}>{shownChildren}</div>
      </div>
    </div>
  );

  return createPortal(<OverlayScope overlay={isTop}>{body}</OverlayScope>, document.body);
}
