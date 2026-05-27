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
    function onClick(e) {
      if (!closeOnBackdrop) return;
      if (wrapRef.current && !wrapRef.current.contains(e.target)) onClose?.();
    }
    function onKey(e) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose?.();
      }
    }
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [visible, onClose, closeOnBackdrop]);

  if (!visible) return null;

  const body = (
    <div className={styles.backdrop}>
      <div
        ref={wrapRef}
        className={styles.modal}
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
        {children}
      </div>
    </div>
  );

  return createPortal(body, document.body);
}
