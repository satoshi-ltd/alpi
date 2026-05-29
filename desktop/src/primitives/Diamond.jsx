export default function Diamond({ color, size, pulse = false, className = "", style }) {
  const sizeClass = size === "md" ? "md" : "";
  return (
    <span
      className={`ds-diamond ${sizeClass} ${pulse ? "pulse-glyph" : ""} ${className}`.trim()}
      aria-hidden
      style={{
        "--c": color || undefined,
        ...style,
      }}
    />
  );
}
