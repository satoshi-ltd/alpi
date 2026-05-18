import styles from "./Activity.module.css";

const DOT = { sm: 3, md: 4, lg: 6, xl: 8 };
const GAP = { sm: 2, md: 3, lg: 4, xl: 6 };

export default function Activity({ size = "md", tint, className = "", style }) {
  return (
    <span
      aria-hidden
      className={`${styles.root} ${className}`.trim()}
      style={{
        "--c": tint || undefined,
        "--dot": `${DOT[size] ?? DOT.md}px`,
        "--gap": `${GAP[size] ?? GAP.md}px`,
        ...style,
      }}
    >
      <span />
      <span />
      <span />
    </span>
  );
}
