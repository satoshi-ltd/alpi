import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import styles from "./ContextMenu.module.css";

export function ContextMenuMount() {
  const [menu, setMenu] = useState(null);
  useEffect(() => {
    window.openContextMenu = (e, items) => {
      e.preventDefault();
      setMenu({ x: e.clientX, y: e.clientY, items });
    };
    window.closeContextMenu = () => setMenu(null);
    return () => {
      delete window.openContextMenu;
      delete window.closeContextMenu;
    };
  }, []);
  if (!menu) return null;
  return (
    <ContextMenu
      x={menu.x}
      y={menu.y}
      items={menu.items}
      onClose={() => setMenu(null)}
    />
  );
}

export default function ContextMenu({ x, y, items, onClose }) {
  const ref = useRef(null);
  const [pos, setPos] = useState({ x, y });

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    let nx = x;
    let ny = y;
    if (x + r.width + 8 > vw) nx = vw - r.width - 8;
    if (y + r.height + 8 > vh) ny = vh - r.height - 8;
    setPos({ x: nx, y: ny });
  }, [x, y]);

  useEffect(() => {
    function onDoc(e) {
      if (!ref.current?.contains(e.target)) onClose();
    }
    function onKey(e) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  return createPortal(
    <div
      ref={ref}
      className={`anim-pop ${styles.root}`}
      role="menu"
      style={{ top: pos.y, left: pos.x }}
    >
      {items.map((it, i) => {
        if (it.kind === "separator") {
          return <div key={`sep-${i}`} role="separator" className={styles.sep} />;
        }
        const danger = it.kind === "danger";
        return (
          <button
            key={it.label}
            type="button"
            role="menuitem"
            onClick={() => {
              it.onClick?.();
              onClose();
            }}
            className={`row ${styles.item} ${danger ? styles.itemDanger : ""}`}
          >
            <span className={`${styles.icon} ${danger ? styles.iconDanger : ""}`}>
              {it.icon}
            </span>
            <span className={styles.label}>{it.label}</span>
            {it.shortcut && (
              <span className={`mono ${styles.shortcut}`}>{it.shortcut}</span>
            )}
          </button>
        );
      })}
    </div>,
    document.body,
  );
}
