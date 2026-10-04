import { ALPACA_FOLD, FOLD_SIZES } from "../../../common/folds.mjs";
import { DisplayHeading, Fold, Mono } from "./index.js";
import styles from "./EmptyState.module.css";

export default function EmptyState({
  fold = ALPACA_FOLD,
  accent,
  heading,
  subtitle,
  children,
}) {
  return (
    <div className={styles.shell}>
      <div className={styles.col}>
        <Fold fold={fold} color={accent || undefined} size={FOLD_SIZES.hero} />
        <DisplayHeading hero>{heading}</DisplayHeading>
        {subtitle && (
          <Mono className={`tnum ${styles.subtitle}`}>{subtitle}</Mono>
        )}
        {children}
      </div>
    </div>
  );
}
