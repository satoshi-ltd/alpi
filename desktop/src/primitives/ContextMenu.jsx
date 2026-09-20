import { navigateMenu } from "../lib/menuNavigation.js";
import { OverlayScope, useOverlay } from "../hooks/useOverlay.js";
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
  const isTop = useOverlay({ open: true, onClose, ref });

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
    setPos({ x: Math.max(8, nx), y: Math.max(8, ny) });
  }, [x, y]);

  useEffect(() => {
    ref.current?.querySelector("button:not(:disabled)")?.focus();
  }, []);

  useEffect(() => {
    function onDoc(e) {
      if (isTop() && !ref.current?.contains(e.target)) onClose();
    }
    document.addEventListener("mousedown", onDoc);
    return () => {
      document.removeEventListener("mousedown", onDoc);
    };
  }, [onClose]);

  return createPortal(
    <OverlayScope overlay={isTop}>
      <div
        ref={ref}
        className={`anim-pop ${styles.root}`}
        role="menu"
        onKeyDown={(event) => navigateMenu(event, ref.current)}
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
              disabled={it.disabled}
              onClick={() => {
                onClose();
                it.onClick?.();
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
      </div>
    </OverlayScope>,
    document.body,
  );
}
