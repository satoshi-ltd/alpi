import { useEffect, useState } from "react";
import styles from "./Skeleton.module.css";

const FLICKER_MS = 150;

// Animated placeholder. Renders nothing for the first FLICKER_MS so fast
// loads don't show a flash of skeleton — only sustained loading triggers it.
export default function Skeleton({
  width = "8em",
  height = "0.8em",
  radius,
  className = "",
  delay = FLICKER_MS,
}) {
  const [show, setShow] = useState(delay === 0);
  useEffect(() => {
    if (delay === 0) return;
    const id = setTimeout(() => setShow(true), delay);
    return () => clearTimeout(id);
  }, [delay]);
  if (!show) return null;
  return (
    <span
      className={`${styles.skeleton} ${className}`}
      style={{ width, height, borderRadius: radius }}
      aria-hidden="true"
    />
  );
}

export function SkeletonRow({ children, className = "" }) {
  return <span className={`${styles.row} ${className}`}>{children}</span>;
}
