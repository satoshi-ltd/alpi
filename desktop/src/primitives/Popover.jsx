import { useEffect, useRef } from "react";

export default function Popover({
  open,
  onClose,
  width = "var(--pop-md)",
  align = "left",
  side = "bottom",
  placement,
  children,
  className = "",
  style,
}) {
  const ref = useRef(null);

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
      if (ref.current && !ref.current.contains(e.target)) onClose?.();
    };
    const onKey = (e) => {
      if (e.key === "Escape") onClose?.();
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      ref={ref}
      className={`anim-pop ${className}`.trim()}
      style={{
        position: "absolute",
        [resolvedSide === "top" ? "bottom" : "top"]: "calc(100% + 8px)",
        [resolvedAlign]: 0,
        width,
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
  );
}
