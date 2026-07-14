import { useEffect, useRef, useState } from "react";

import styles from "./LazyMount.module.css";

// Mount-on-approach: children (and their fetch effects) don't exist until the block nears the viewport.
export default function LazyMount({ children, rootMargin = "250px", placeholder = null }) {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (visible) return undefined;
    const el = ref.current;
    if (!el) return undefined;
    if (typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return undefined;
    }
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) setVisible(true);
      },
      { rootMargin },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [visible, rootMargin]);
  if (visible) return children;
  return <div ref={ref} className={styles.hold}>{placeholder}</div>;
}
