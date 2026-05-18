import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { CaretIcon } from "./icons.jsx";
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
  portal = false,
  fullWidth = false,
  children,
}) {
  const [open, setOpen] = useState(false);
  const [resolved, setResolved] = useState({ direction, align, ready: false });
  const ref = useRef(null);
  const triggerRef = useRef(null);
  const menuRef = useRef(null);
  const onOpenChangeRef = useRef(onOpenChange);

  useEffect(() => {
    onOpenChangeRef.current = onOpenChange;
  }, [onOpenChange]);

  useEffect(() => {
    function onClick(e) {
      const inTrigger = ref.current && ref.current.contains(e.target);
      const inMenu = menuRef.current && menuRef.current.contains(e.target);
      if (!inTrigger && !inMenu) {
        setOpen(false);
      }
    }
    function onKey(e) {
      if (e.key === "Escape" && open) {
        e.preventDefault();
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  useEffect(() => {
    onOpenChangeRef.current?.(open);
    if (!open) setResolved((r) => ({ ...r, ready: false }));
  }, [open]);

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

    const top = dir === "up" ? t.top - m.height - 6 : t.bottom + 6;
    const left = al === "left" ? t.left : t.right - m.width;

    setResolved({ direction: dir, align: al, ready: true, top, left });
  }, [open, direction, align, portal]);

  const close = () => setOpen(false);
  const dir = resolved.ready ? resolved.direction : direction;
  const al = resolved.ready ? resolved.align : align;

  const menu =
    open && (
      <div
        ref={menuRef}
        className={`${styles.menu} ${portal ? styles.menuPortal : ""}`}
        style={
          portal
            ? {
                width,
                top: resolved.top ?? 0,
                left: resolved.left ?? 0,
                visibility: resolved.ready ? "visible" : "hidden",
              }
            : {
                width,
                [dir === "up" ? "bottom" : "top"]: "calc(100% + 6px)",
                [al]: 0,
                visibility: resolved.ready ? "visible" : "hidden",
              }
        }
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
    );

  return (
    <div className={`${styles.wrap} ${fullWidth ? styles.wrapFull : ""}`.trim()} ref={ref}>
      <button
        ref={triggerRef}
        className={`${styles.trigger} ${variantClass(variant)} ${open ? styles.triggerOpen : ""}`}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        {trigger.leading && (
          <span className={styles.leading}>{trigger.leading}</span>
        )}
        {trigger.caption ? (
          <span className={styles.labelStack}>
            <span className={styles.label}>{trigger.label}</span>
            <span className={styles.caption}>{trigger.caption}</span>
          </span>
        ) : (
          <span className={styles.label}>{trigger.label}</span>
        )}
        <CaretIcon className={styles.caret} />
      </button>

      {portal ? createPortal(menu, document.body) : menu}
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

function variantClass(variant) {
  if (variant === "field" || variant === "outlined") return styles.triggerField;
  if (variant === "list") return styles.triggerList;
  return "";
}

Dropdown.Group = Group;
Dropdown.Row = Row;
Dropdown.Empty = Empty;
