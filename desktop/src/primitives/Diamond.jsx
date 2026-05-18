export default function Diamond({ color, size = 9, className = "", style }) {
  return (
    <span
      className={`ds-diamond ${className}`.trim()}
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
