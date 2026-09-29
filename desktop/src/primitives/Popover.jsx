import { OverlayScope, useOverlay } from "../hooks/useOverlay.js";
import { navigateMenu } from "../lib/menuNavigation.js";
import { useEffect, useRef } from "react";

// Action menus size to their content; forms and pickers pass a --pop-* token because inputs stretch to fill.
export default function Popover({
  open,
  onClose,
  width = "max-content",
  align = "left",
  side = "bottom",
  placement,
  children,
  className = "",
  style,
  navigable = false,
  role,
}) {
  const ref = useRef(null);
  const isTop = useOverlay({ open, onClose, ref });

  let resolvedAlign = align;
  let resolvedSide = side;
  if (placement) {
    const [s, a] = placement.split("-");
    resolvedSide = s === "top" ? "top" : "bottom";
    resolvedAlign = a === "end" ? "right" : "left";
  }

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (e) => {
      // Wrapper (trigger + panel), not just the panel — else a trigger click closes here and its own handler re-opens.
      const host = ref.current?.parentElement ?? ref.current;
      if (isTop() && host && !host.contains(e.target)) onClose?.();
    };
    document.addEventListener("mousedown", onDoc);
    return () => {
      document.removeEventListener("mousedown", onDoc);
    };
  }, [open, onClose]);

  useEffect(() => {
    if (open && navigable) ref.current?.querySelector("button:not(:disabled)")?.focus();
  }, [open, navigable]);

  if (!open) return null;
  return (
    <OverlayScope overlay={isTop}>
      <div
        ref={ref}
        role={role}
        onKeyDown={navigable ? (event) => navigateMenu(event, ref.current) : undefined}
        className={`anim-pop ${className}`.trim()}
        style={{
          position: "absolute",
          [resolvedSide === "top" ? "bottom" : "top"]: "calc(100% + 8px)",
          [resolvedAlign]: 0,
          width,
          maxWidth: "min(var(--pop-lg), calc(100vw - 16px))",
          background: "var(--bg-elev)",
          border: ".5px solid var(--line-2)",
          borderRadius: "var(--r-xl)",
          boxShadow: "var(--shadow)",
          zIndex: 50,
          overflow: "hidden",
          ...style,
        }}
      >
        {children}
      </div>
    </OverlayScope>
  );
}
