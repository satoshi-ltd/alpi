import { CaretIcon } from "./icons.jsx";
import styles from "./JumpToLatest.module.css";

export default function JumpToLatest({ show, onClick }) {
  return (
    <button
      type="button"
      className={`${styles.btn} ${show ? styles.visible : ""}`.trim()}
      onClick={onClick}
      aria-label="Scroll to latest"
      title="Jump to latest"
      aria-hidden={!show}
      tabIndex={show ? 0 : -1}
    >
      <CaretIcon size={14} color="currentColor" />
    </button>
  );
}
