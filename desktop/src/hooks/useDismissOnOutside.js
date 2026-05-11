import { useEffect } from "react";

// Closes a popover on Esc or outside-click. Used by every dropdown popover
// in Settings (TCP port editor, peer detail, budget editor, etc.) — Modal
// has its own equivalent built in.
export function useDismissOnOutside({ open, onClose, wrapRef }) {
  useEffect(() => {
    if (!open) return;
    function onKey(e) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose?.();
      }
    }
    function onClick(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) onClose?.();
    }
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, onClose, wrapRef]);
}
