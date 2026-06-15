import { SkParagraph } from "../primitives/Skeleton.jsx";
import Activity from "../primitives/Activity.jsx";
import styles from "./ChatSkeletons.module.css";

export function ChatLoadSkeleton() {
  return (
    <div className={`${styles.load} anim-fade`} aria-hidden="true">
      <SkParagraph lg widths={["88%", "100%", "96%", "62%"]} />
      <div className={styles.userRow}>
        <div className={styles.userBubble}>
          <SkParagraph widths={["90%", "64%"]} />
        </div>
      </div>
      <SkParagraph lg widths={["80%", "97%", "88%", "100%", "48%"]} />
      <SkParagraph lg widths={["94%", "70%"]} />
    </div>
  );
}

export function PendingReplySkeleton() {
  return (
    <div className={`${styles.pending} anim-fade`}>
      <div className={styles.status}>
        <Activity size="md" tint="var(--ink-3)" />
        <span className={styles.thinkingLabel}>thinking…</span>
      </div>
      <SkParagraph lg widths={["92%", "100%", "74%"]} />
    </div>
  );
}
