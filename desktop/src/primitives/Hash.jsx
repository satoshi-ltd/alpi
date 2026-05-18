// Hash — workgroup identity glyph. Mono `#` with optional size override.
export default function Hash({ size, color, className = "", style, children = "#" }) {
  return (
    <span
      className={`ds-hash ${className}`.trim()}
      aria-hidden
      style={{ fontSize: size, color: color || undefined, ...style }}
    >
      {children}
    </span>
  );
}
