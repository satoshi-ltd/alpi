import { useCallback, useRef, useState } from "react";
import { createPortal } from "react-dom";

export default function Tip({
  text,
  side = "down",
  children,
  block = false,
  escape = false,
  style,
  wide = false,
}) {
  if (!text) return children;
  const sideClass =
    side === "up-r"
      ? "up r"
      : side === "up-l"
        ? "up l"
        : side === "r"
          ? "r"
          : side === "l"
            ? "l"
            : side === "up"
              ? "up"
              : "";
  const bodyClass = [`ds-tip-body`, sideClass, wide ? "ds-tip-wide" : ""].filter(Boolean).join(" ");
  const wrapStyle = {
    display: block ? "flex" : "inline-flex",
    width: block ? "100%" : "auto",
    ...style,
  };

  if (!escape) {
    return (
      <span className="ds-tip" style={wrapStyle}>
        {children}
        <span className={bodyClass}>{text}</span>
      </span>
    );
  }

  return (
    <TipEscape
      text={text}
      bodyClass={bodyClass}
      sideClass={sideClass}
      wrapStyle={wrapStyle}
    >
      {children}
    </TipEscape>
  );
}

function TipEscape({ text, bodyClass, sideClass, wrapStyle, children }) {
  const triggerRef = useRef(null);
  const [hovered, setHovered] = useState(false);
  const [coords, setCoords] = useState(null);
  const sides = sideClass.split(" ").filter(Boolean);
  const isUp = sides.includes("up");
  const anchor = sides.includes("r") ? "right" : sides.includes("l") ? "left" : "center";

  const onEnter = useCallback(() => {
    const r = triggerRef.current?.getBoundingClientRect();
    if (!r) return;
    setCoords({ rect: r });
    setHovered(true);
  }, []);
  const onLeave = useCallback(() => setHovered(false), []);

  let bodyStyle = { position: "fixed", pointerEvents: "none", zIndex: 100, opacity: 1 };
  if (coords) {
    const { rect } = coords;
    if (isUp) bodyStyle.bottom = window.innerHeight - rect.top + 6;
    else      bodyStyle.top    = rect.bottom + 6;
    if (anchor === "right") bodyStyle.right = window.innerWidth - rect.right;
    else if (anchor === "left") bodyStyle.left = rect.left;
    else { bodyStyle.left = rect.left + rect.width / 2; bodyStyle.transform = "translateX(-50%)"; }
  }

  return (
    <span
      ref={triggerRef}
      className="ds-tip ds-tip-escape"
      style={wrapStyle}
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
    >
      {children}
      {hovered && coords && createPortal(
        <span className={bodyClass} style={bodyStyle}>{text}</span>,
        document.body,
      )}
    </span>
  );
}
