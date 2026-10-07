import { useEffect, useState } from "react";

const DURATION_MS = 800;

export default function RefreshBar({
  active,
  controlled = false,
  label = null,
}) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (controlled) return undefined;
    if (!active) return undefined;
    setVisible(true);
    const t = setTimeout(() => setVisible(false), DURATION_MS);
    return () => clearTimeout(t);
  }, [active, controlled]);

  if (!(controlled ? active : visible)) return null;
  return (
    <span
      className="refresh-bar"
      data-controlled={controlled || undefined}
      role={label ? "progressbar" : undefined}
      aria-label={label || undefined}
      aria-hidden={label ? undefined : true}
    >
      <i />
    </span>
  );
}
