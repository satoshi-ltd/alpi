export default function Dot({ color, size = 7, pulse = false, className = "", style }) {
  return (
    <span
      className={`ds-dot ${pulse ? "pulse-dot" : ""} ${className}`.trim()}
      aria-hidden
      style={{
        "--c": color || undefined,
        width: size,
        height: size,
        ...style,
      }}
    />
  );
}
