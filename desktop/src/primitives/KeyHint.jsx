import Kbd from "./Kbd.jsx";
import { keyTokens } from "../lib/shortcuts.js";
import styles from "./KeyHint.module.css";

export default function KeyHint({ hint, className = "" }) {
  if (!hint) return null;
  const tokens = keyTokens(hint);
  if (!tokens) {
    return <span className={`${styles.text} ${className}`.trim()}>{hint}</span>;
  }
  return (
    <span className={`${styles.keys} ${className}`.trim()} data-keys={hint}>
      {tokens.map((t, i) => <Kbd key={i}>{t}</Kbd>)}
    </span>
  );
}
