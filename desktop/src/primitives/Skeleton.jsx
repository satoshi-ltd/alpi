import { useEffect, useState } from "react";
import styles from "./Skeleton.module.css";

const FLICKER_MS = 150;

// Renders nothing for the first FLICKER_MS so a fast load never flashes a skeleton.
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

export function SkLine({ lg = false, width = "100%", delay = 0, className = "" }) {
  return (
    <div
      aria-hidden="true"
      className={`${styles.skLine} ${lg ? styles.skLineLg : ""} ${className}`.trim()}
      style={{ width, animationDelay: `${Math.round(delay * 100) / 100}s` }}
    />
  );
}

// widths drive each line — vary them and end short (a real paragraph), never all-equal.
export function SkParagraph({ widths, lg = false, className = "" }) {
  return (
    <div aria-hidden="true" className={`${styles.skPara} ${className}`.trim()}>
      {widths.map((w, i) => (
        <SkLine key={i} lg={lg} width={w} delay={i * 0.12} />
      ))}
    </div>
  );
}
