import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

import IconBtn from "./IconBtn.jsx";
import Tip from "./Tip.jsx";
import { XIcon } from "./icons.jsx";
import styles from "./Modal.module.css";

export default function Modal({
  open,
  onClose,
  title,
  width,
  closeOnBackdrop = true,
  closeButton = false,
  children,
}) {
  const wrapRef = useRef(null);
  const controlled = open !== undefined;
  const visible = !controlled || open;

  useEffect(() => {
    if (!visible) return undefined;
    function onKey(e) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose?.();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
    };
  }, [visible, onClose]);

  const openerRef = useRef(null);
  const prevVisibleRef = useRef(false);
  if (visible && !prevVisibleRef.current) {
    openerRef.current = typeof document !== "undefined" ? document.activeElement : null;
  }
  prevVisibleRef.current = visible;

  useEffect(() => {
    if (!visible) return undefined;
    return () => {
      const opener = openerRef.current;
      setTimeout(() => {
        if (opener && document.contains(opener)) opener.focus?.();
      }, 0);
    };
  }, [visible]);

  if (!visible) return null;

  const body = (
    <div
      className={`anim-overlay ${styles.backdrop}`}
      onMouseDown={(e) => {
        if (closeOnBackdrop && e.target === e.currentTarget) onClose?.();
      }}
    >
      <div
        ref={wrapRef}
        className={`anim-dialog ${styles.modal}`}
        style={width ? { width, minWidth: width, maxWidth: width } : undefined}
      >
        {(title || closeButton) && (
          <div className={styles.titleRow}>
            {title && <div className={styles.title}>{title}</div>}
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

  return createPortal(body, document.body);
}
