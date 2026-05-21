// context-menu.jsx — right-click context menu (cursor-anchored).
// Items: { label, icon, kind: 'action'|'separator'|'danger', shortcut?, onClick? }

const { useState: useStateCM, useEffect: useEffectCM, useRef: useRefCM } = React;

function ContextMenu({ x, y, items, onClose }) {
  const ref = useRefCM(null);
  const [pos, setPos] = useStateCM({ x, y });

  useEffectCM(() => {
    // Clamp inside viewport after first render
    if (!ref.current) return;
    const r = ref.current.getBoundingClientRect();
    const vw = window.innerWidth, vh = window.innerHeight;
    let nx = x, ny = y;
    if (x + r.width + 8 > vw)  nx = vw - r.width - 8;
    if (y + r.height + 8 > vh) ny = vh - r.height - 8;
    setPos({ x: nx, y: ny });
  }, []);

  useEffectCM(() => {
    const onDoc = (e) => { if (!ref.current?.contains(e.target)) onClose(); };
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('mousedown', onDoc); document.removeEventListener('keydown', onKey); };
  }, [onClose]);

  return (
    <div
      ref={ref}
      className="anim-pop"
      style={{
        position: 'fixed', top: pos.y, left: pos.x, zIndex: 200,
        width: 220, background: 'var(--bg-elev)',
        border: '.5px solid var(--line-2)', borderRadius: 10,
        boxShadow: 'var(--shadow)', padding: 4,
        transformOrigin: 'top left',
      }}
    >
      {items.map((it, i) => {
        if (it.kind === 'separator') {
          return <div key={i} style={{ height: 1, background: 'var(--line)', margin: '4px 6px' }} />;
        }
        const isDanger = it.kind === 'danger';
        return (
          <button
            key={i}
            onClick={() => { it.onClick?.(); onClose(); }}
            className="row"
            style={{
              width: '100%', padding: '6px 10px', borderRadius: 6,
              gap: 10, textAlign: 'left', alignItems: 'center',
              color: isDanger ? 'var(--c-danger)' : 'var(--ink)',
            }}
            onMouseEnter={e => e.currentTarget.style.background = isDanger
              ? 'color-mix(in srgb, var(--c-danger) 10%, transparent)'
              : 'var(--hover)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            <span style={{ width: 14, display: 'inline-flex', justifyContent: 'center', color: isDanger ? 'var(--c-danger)' : 'var(--ink-3)' }}>
              {it.icon}
            </span>
            <span style={{ flex: 1, fontSize: 13 }}>{it.label}</span>
            {it.shortcut && <span className="mono" style={{ fontSize: 11, color: 'var(--ink-4)' }}>{it.shortcut}</span>}
          </button>
        );
      })}
    </div>
  );
}

// Global mount — listens for openContextMenu events
function ContextMenuMount() {
  const [menu, setMenu] = useStateCM(null);
  useEffectCM(() => {
    window.openContextMenu = (e, items) => {
      e.preventDefault();
      setMenu({ x: e.clientX, y: e.clientY, items });
    };
    window.closeContextMenu = () => setMenu(null);
  }, []);
  if (!menu) return null;
  return <ContextMenu x={menu.x} y={menu.y} items={menu.items} onClose={() => setMenu(null)} />;
}

window.ContextMenu = ContextMenu;
window.ContextMenuMount = ContextMenuMount;

// Pin icon — small, used in sidebar rows + chat header
function PinIcon({ filled = false, ...props }) {
  return (
    <svg viewBox="0 0 16 16" {...props} style={{ width: 13, height: 13, stroke: 'currentColor', fill: filled ? 'currentColor' : 'none', strokeWidth: 1.5, strokeLinecap: 'round', strokeLinejoin: 'round', ...(props.style || {}) }}>
      <path d="M9.5 2.5l4 4-2 .5-2.5 2.5.5 3-2.5-2.5L3 13l3-4-2.5-2.5 3 .5L9 4l.5-1.5z" />
    </svg>
  );
}
window.PinIcon = PinIcon;
