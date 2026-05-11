import { useEffect, useRef } from "react";
import styles from "./Modal.module.css";

export default function Modal({ onClose, title, children }) {
  const wrapRef = useRef(null);

  useEffect(() => {
    function onClick(e) {
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
  }, [onClose]);

  return (
    <div className={styles.backdrop}>
      <div ref={wrapRef} className={styles.modal}>
        {title && <div className={styles.title}>{title}</div>}
        {children}
      </div>
    </div>
  );
}
