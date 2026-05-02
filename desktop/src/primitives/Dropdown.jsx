import { useEffect, useLayoutEffect, useRef, useState } from "react";
import styles from "./Dropdown.module.css";

export default function Dropdown({
  trigger,
  direction = "down",
  align = "right",
  width = 280,
  variant = "default",
  searchable = false,
  searchPlaceholder = "Find…",
  query = "",
  onQueryChange,
  onOpenChange,
  children,
}) {
  const [open, setOpen] = useState(false);
  const [resolved, setResolved] = useState({ direction, align, ready: false });
  const ref = useRef(null);
  const triggerRef = useRef(null);
  const menuRef = useRef(null);

  useEffect(() => {
    function onClick(e) {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  useEffect(() => {
    onOpenChange?.(open);
    if (!open) setResolved((r) => ({ ...r, ready: false }));
  }, [open, onOpenChange]);

  useLayoutEffect(() => {
    if (!open || !triggerRef.current || !menuRef.current) return;
    const t = triggerRef.current.getBoundingClientRect();
    const m = menuRef.current.getBoundingClientRect();
    const vh = window.innerHeight;
    const vw = window.innerWidth;
    const margin = 12;

    let dir = direction;
    const fitsBelow = t.bottom + m.height + margin <= vh;
    const fitsAbove = t.top - m.height - margin >= 0;
    if (dir === "down" && !fitsBelow && fitsAbove) dir = "up";
    if (dir === "up" && !fitsAbove && fitsBelow) dir = "down";

    let al = align;
    const fitsRight = t.left + m.width + margin <= vw;
    const fitsLeft = t.right - m.width - margin >= 0;
    if (al === "left" && !fitsRight && fitsLeft) al = "right";
    if (al === "right" && !fitsLeft && fitsRight) al = "left";

    setResolved({ direction: dir, align: al, ready: true });
  }, [open, direction, align]);

  const close = () => setOpen(false);
  const dir = resolved.ready ? resolved.direction : direction;
  const al = resolved.ready ? resolved.align : align;

  return (
    <div className={styles.wrap} ref={ref}>
      <button
        ref={triggerRef}
        className={`${styles.trigger} ${
          variant === "outlined" ? styles.triggerOutlined : ""
        }`}
        onClick={() => setOpen((v) => !v)}
      >
        {trigger.leading}
        <span className={styles.label}>{trigger.label}</span>
        <Caret />
      </button>

      {open && (
        <div
          ref={menuRef}
          className={styles.menu}
          style={{
            width,
            [dir === "up" ? "bottom" : "top"]: "calc(100% + 6px)",
            [al]: 0,
            visibility: resolved.ready ? "visible" : "hidden",
          }}
        >
          {searchable && (
            <div className={styles.searchWrap}>
              <input
                className={styles.search}
                placeholder={searchPlaceholder}
                value={query}
                onChange={(e) => onQueryChange?.(e.target.value)}
                autoFocus
              />
            </div>
          )}
          <div className={styles.list}>
            {typeof children === "function" ? children({ close }) : children}
          </div>
        </div>
      )}
    </div>
  );
}

function Group({ label, children }) {
  return (
    <div className={styles.group}>
      {label && <div className={styles.groupLabel}>{label}</div>}
      {children}
    </div>
  );
}

function Row({
  active,
  disabled,
  onClick,
  leading,
  trailing,
  caption,
  children,
}) {
  return (
    <button
      className={`${styles.row} ${active ? styles.rowActive : ""}`}
      onClick={onClick}
      disabled={disabled}
    >
      {leading && <span className={styles.rowLeading}>{leading}</span>}
      <span className={styles.rowMain}>
        <span className={styles.rowName}>{children}</span>
        {caption && <span className={styles.rowCaption}>{caption}</span>}
      </span>
      {trailing && <span className={styles.rowTrailing}>{trailing}</span>}
    </button>
  );
}

function Empty({ children }) {
  return <div className={styles.emptyRow}>{children}</div>;
}

Dropdown.Group = Group;
Dropdown.Row = Row;
Dropdown.Empty = Empty;

function Caret() {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
      <path
        d="M2 4l3 3 3-3"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
