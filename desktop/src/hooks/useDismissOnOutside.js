import { useEffect } from "react";
import { useOverlay } from "./useOverlay.js";

export function useDismissOnOutside({ open, onClose, wrapRef }) {
  const isTop = useOverlay({ open, onClose, ref: wrapRef });
  useEffect(() => {
    if (!open) return;
    function onClick(e) {
      if (isTop() && wrapRef.current && !wrapRef.current.contains(e.target)) onClose?.();
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open, onClose, wrapRef, isTop]);
}
