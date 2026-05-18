export default function Tip({ text, side = "down", children, block = false, style }) {
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
  return (
    <span
      className="ds-tip"
      style={{
        display: block ? "flex" : "inline-flex",
        width: block ? "100%" : "auto",
        ...style,
      }}
    >
      {children}
      <span className={`ds-tip-body ${sideClass}`.trim()}>{text}</span>
    </span>
  );
}
