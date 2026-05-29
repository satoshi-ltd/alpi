import { useMemo } from "react";
import Skeleton from "./Skeleton.jsx";
import styles from "./MessageSkeleton.module.css";

// Widths chosen once per mount so re-renders don't jitter the placeholder.
export default function MessageSkeleton({ className = "" }) {
  const widths = useMemo(() => {
    const lines = 2 + Math.round(Math.random());
    const pick = (min, max) => `${Math.round(min + Math.random() * (max - min))}%`;
    const ranges = [[80, 100], [55, 85], [30, 60]];
    return Array.from({ length: lines }, (_, i) => pick(...ranges[i]));
  }, []);
  return (
    <div className={`${styles.root} ${className}`.trim()}>
      {widths.map((w, i) => (
        <Skeleton key={i} width={w} height="0.9em" delay={i === 0 ? 0 : 80 * i} />
      ))}
    </div>
  );
}
