import Bar from "./Bar.jsx";
import Tip from "./Tip.jsx";

export default function MeterChip({
  value,
  pct = 0,
  color,
  showPercent = true,
  tip,
  tipSide = "down",
  className = "",
}) {
  const p = Math.max(0, Math.min(1, pct));
  const chip = (
    <span className={`ds-meter ${className}`.trim()}>
      <span className="val">{value}</span>
      <Bar pct={p} color={color} />
      {showPercent && <span className="pct">{Math.round(p * 100)}%</span>}
    </span>
  );
  if (!tip) return chip;
  return (
    <Tip text={tip} side={tipSide}>
      {chip}
    </Tip>
  );
}
