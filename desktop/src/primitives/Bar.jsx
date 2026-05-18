export default function Bar({ pct = 0, color, width = 56, height = 5, className = "", style }) {
  const p = Math.max(0, Math.min(1, pct));
  return (
    <span
      className={`ds-bar ${className}`.trim()}
      role="progressbar"
      aria-valuenow={Math.round(p * 100)}
      style={{ width, height, ...style }}
    >
      <i style={{ width: `${p * 100}%`, background: color || undefined }} />
    </span>
  );
}
