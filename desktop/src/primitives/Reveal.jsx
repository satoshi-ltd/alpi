import { useState } from "react";
import styles from "./Reveal.module.css";

export default function Reveal({ open, children, className = "" }) {
  const [mounted, setMounted] = useState(open);
  if (open && !mounted) setMounted(true);
  return (
    <div className={`${styles.reveal} ${open ? styles.open : ""} ${className}`.trim()} inert={!open} data-open={open ? "true" : "false"}>
      <div className={styles.inner}>{mounted ? children : null}</div>
    </div>
  );
}
