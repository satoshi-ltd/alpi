import { TWIN } from "../lib/brandMark.js";
import { MARK_SIZES } from "../../../common/agentMarks.mjs";
import { Button, DisplayHeading, Fold, PlusIcon } from "./index.js";
import styles from "./EmptyState.module.css";

export default function EmptyState({
  shape = TWIN,
  accent,
  heading,
  subtitle,
  action = null,
  children,
}) {
  return (
    <div className={styles.shell}>
      <div className={styles.col}>
        <Fold shape={shape} color={accent || undefined} size={MARK_SIZES.hero} />
        <DisplayHeading hero>{heading}</DisplayHeading>
        {subtitle && (
          <span className={`tnum ${styles.subtitle}`}>{subtitle}</span>
        )}
        {action && (
          <Button variant="primary" icon={<PlusIcon />} onClick={action.onClick}>{action.label}</Button>
        )}
        {children}
      </div>
    </div>
  );
}
