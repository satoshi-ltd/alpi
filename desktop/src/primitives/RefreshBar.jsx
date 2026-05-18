import { useEffect, useState } from "react";

const DURATION_MS = 800;

export default function RefreshBar({ active, accent }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!active) return undefined;
    setVisible(true);
    const t = setTimeout(() => setVisible(false), DURATION_MS);
    return () => clearTimeout(t);
  }, [active]);

  if (!visible) return null;
  return (
    <span
      className="refresh-bar"
      style={accent ? { "--c": accent } : undefined}
      aria-hidden
    >
      <i />
    </span>
  );
}
