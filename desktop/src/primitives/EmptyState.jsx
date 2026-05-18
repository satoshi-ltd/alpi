import { Logo, DisplayHeading, Mono } from "./index.js";
import styles from "./EmptyState.module.css";

export default function EmptyState({
  glyph = "logo",
  accent,
  heading,
  subtitle,
  children,
}) {
  return (
    <div className={styles.shell}>
      <div className={styles.col}>
        {glyph === "logo" && <Logo />}
        {glyph === "diamond" && (
          <span
            aria-hidden
            className={styles.diamond}
            style={accent ? { "--c": accent } : undefined}
          />
        )}
        {glyph === "hash" && (
          <span aria-hidden className={styles.hash}>
            #
          </span>
        )}
        <DisplayHeading hero>{heading}</DisplayHeading>
        {subtitle && (
          <Mono className={`tnum ${styles.subtitle}`}>{subtitle}</Mono>
        )}
        {children}
      </div>
    </div>
  );
}
