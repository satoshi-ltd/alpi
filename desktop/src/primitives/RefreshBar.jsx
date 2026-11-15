import { useEffect, useState } from "react";
import { nameVars } from "../lib/nameVars.js";

const DURATION_MS = 800;

export function barVars(color) {
  if (!color) return undefined;
  const tones = nameVars(color);
  return tones
    ? { "--c-light": tones["--name-light"], "--c-dark": tones["--name-dark"] }
    : { "--c-light": color, "--c-dark": color };
}

export default function RefreshBar({
  active,
  controlled = false,
  label = null,
  color = null,
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
      style={barVars(color)}
    >
      <i />
    </span>
  );
}
