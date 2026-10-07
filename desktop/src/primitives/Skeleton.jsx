import { useEffect, useState } from "react";
import styles from "./Skeleton.module.css";

export const FLICKER_MS = 150;

function useAppear(delay) {
  const [show, setShow] = useState(delay === 0);
  useEffect(() => {
    if (delay === 0) return undefined;
    const id = setTimeout(() => setShow(true), delay);
    return () => clearTimeout(id);
  }, [delay]);
  return show;
}

// Renders nothing for the first FLICKER_MS so a fast load never flashes a skeleton.
export default function Skeleton({
  width = "8em",
  height = "0.8em",
  radius,
  className = "",
  delay = FLICKER_MS,
  label = null,
}) {
  const show = useAppear(delay);
  if (!show) return null;
  return (
    <span
      className={`${styles.skeleton} ${className}`}
      style={{ width, height, borderRadius: radius }}
      role={label ? "img" : undefined}
      aria-label={label || undefined}
      aria-hidden={label ? undefined : "true"}
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

const ROW_WIDTHS = [["46%", "72%"], ["58%", "64%"], ["40%", "78%"], ["52%", "60%"]];

export function SkeletonRows({ count = 4, label = null, as: Tag = "div", mark = true, delay = FLICKER_MS, className = "" }) {
  const show = useAppear(delay);
  if (!show) return null;
  const a11y = label ? { role: "status", "aria-label": label } : { role: "presentation", "aria-hidden": "true" };
  return (
    <Tag {...a11y} className={`${styles.rows} ${className}`.trim()}>
      {Array.from({ length: count }, (_, i) => {
        const [head, sub] = ROW_WIDTHS[i % ROW_WIDTHS.length];
        return (
          <div key={i} className={styles.listRow} aria-hidden="true">
            {mark ? <div className={styles.skMark} /> : null}
            <div className={styles.listText}>
              <SkLine width={head} delay={i * 0.12} />
              <SkLine width={sub} delay={i * 0.12 + 0.06} className={styles.skLineSm} />
            </div>
          </div>
        );
      })}
    </Tag>
  );
}

export function SkeletonReader({ label = null, heading = true, lines = ["92%", "84%", "88%", "56%"], delay = FLICKER_MS, className = "" }) {
  const show = useAppear(delay);
  if (!show) return null;
  return (
    <div {...(label ? { role: "img", "aria-label": label } : { "aria-hidden": "true" })} className={`${styles.reader} ${className}`.trim()}>
      {heading ? <SkLine lg width="34%" /> : null}
      <SkParagraph widths={lines} />
    </div>
  );
}
