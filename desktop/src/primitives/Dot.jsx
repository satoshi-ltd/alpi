export default function Dot({ color, pulse = false, className = "", style }) {
  return (
    <span
      className={`ds-dot ${pulse ? "pulse-dot" : ""} ${className}`.trim()}
      aria-hidden
      style={{
        "--c": color || undefined,
        ...style,
      }}
    />
  );
}
