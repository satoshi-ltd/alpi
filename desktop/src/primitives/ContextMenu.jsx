import useExit from "../hooks/useExit.js";
import { navigateMenu } from "../lib/menuNavigation.js";
import { OverlayScope, useOverlay } from "../hooks/useOverlay.js";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { MenuSeparator, menuRowClass } from "./Menu.jsx";
import styles from "./ContextMenu.module.css";

export function ContextMenuMount() {
  const [menu, setMenu] = useState(null);
  const last = useRef(menu);
  const serial = useRef(0);
  if (menu) last.current = menu;
  const { mounted, closing } = useExit(!!menu);
  useEffect(() => {
    window.openContextMenu = (e, items) => {
      e.preventDefault();
      setMenu({ x: e.clientX, y: e.clientY, items, id: (serial.current += 1) });
    };
    window.closeContextMenu = () => setMenu(null);
    return () => {
      delete window.openContextMenu;
      delete window.closeContextMenu;
    };
  }, []);
  if (!mounted) return null;
  const shown = menu ?? last.current;
  return (
    <ContextMenu
      key={shown.id}
      x={shown.x}
      y={shown.y}
      items={shown.items}
      closing={closing}
      onClose={() => setMenu(null)}
    />
  );
}

export default function ContextMenu({ x, y, items, onClose, closing = false }) {
  const ref = useRef(null);
  const [pos, setPos] = useState({ x, y });
  const isTop = useOverlay({ open: !closing, onClose, ref });

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const r = { width: el.offsetWidth, height: el.offsetHeight };
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
        className={`${closing ? "anim-menu-out" : "anim-menu"} ${styles.root}`}
        role="menu"
        inert={closing || undefined}
        onKeyDown={(event) => navigateMenu(event, ref.current)}
        style={{ top: pos.y, left: pos.x }}
      >
        {items.map((it, i) => {
          if (it.kind === "separator") {
            return <MenuSeparator key={`sep-${i}`} />;
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
              className={menuRowClass({ danger })}
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
