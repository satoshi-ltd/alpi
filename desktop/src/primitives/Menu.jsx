import Icon from "./Icon.jsx";
import styles from "./Menu.module.css";

export function menuRowClass({ selected = false, danger = false, className = "" } = {}) {
  return [styles.row, selected && styles.rowSelected, danger && styles.danger, className]
    .filter(Boolean)
    .join(" ");
}

export function MenuCheck({ on = false }) {
  return (
    <span className={styles.check} aria-hidden>
      {on && <Icon name="check" size={14} />}
    </span>
  );
}

export function MenuSeparator({ inset = false }) {
  return <div role="separator" className={`${styles.sep} ${inset ? styles.sepInset : ""}`.trim()} />;
}
