import { memo } from "react";
import { AlpiIcon } from "./icons.jsx";
import styles from "./NavRow.module.css";

// Shared sidebar row primitive used by both the chat sidebar and Settings aside.
function NavRowImpl({
  active = false,
  accent = null,
  muted = false,
  leading = null,
  trailing = null,
  onClick,
  children,
  ...rest
}) {
  const activeStyle = active && accent
    ? { backgroundColor: `color-mix(in srgb, ${accent} 14%, transparent)` }
    : undefined;
  return (
    <button
      type="button"
      className={`${styles.row} ${active ? styles.rowActive : ""}`}
      onClick={onClick}
      style={activeStyle}
      data-muted={muted ? "1" : undefined}
      {...rest}
    >
      {leading !== null && <span className={styles.leading}>{leading}</span>}
      <span className={styles.name}>{children}</span>
      {trailing}
    </button>
  );
}

const NavRow = memo(NavRowImpl);
export default NavRow;

export const Dot = memo(function Dot({ color }) {
  return (
    <AlpiIcon className={styles.dot} color={color ?? undefined} />
  );
});

export const Hash = memo(function Hash({ children = "#" }) {
  return <span className={styles.hash}>{children}</span>;
});

export const AccentDot = memo(function AccentDot({ color }) {
  return (
    <span
      className={styles.accentDot}
      style={{ backgroundColor: color || "var(--color-accent)" }}
    />
  );
});
