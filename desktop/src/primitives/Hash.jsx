export default function Hash({ size, color, pulse = false, className = "", style, children = "#" }) {
  const sizeClass = size === "md" ? "md" : "";
  return (
    <span
      className={`ds-hash ${sizeClass} ${pulse ? "pulse-glyph" : ""} ${className}`.trim()}
      aria-hidden
      style={{ color: color || undefined, ...style }}
    >
      {children}
    </span>
  );
}
