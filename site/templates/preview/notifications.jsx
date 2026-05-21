// notifications.jsx — bottom-right toast stack.
// Pill shape, status dot, optional action. Auto-dismiss; hover pauses timer.
//
// Global API:
//   window.notify("text")                      → info
//   window.notify("text", { kind: 'success' }) → green dot, pulsing
//   window.notify({ text, kind, action, onAction, duration, persistent })

const { useState: useStateN, useEffect: useEffectN, useRef: useRefN } = React;

function NotificationStack() {
  const [items, setItems] = useStateN([]);

  useEffectN(() => {
    // Expose the global notify API
    window.notify = (textOrOpts, opts) => {
      const o = typeof textOrOpts === 'string'
        ? { text: textOrOpts, ...(opts || {}) }
        : textOrOpts;
      const n = {
        id: Math.random().toString(36).slice(2, 9),
        text: o.text,
        kind: o.kind || 'info',
        action: o.action,
        onAction: o.onAction,
        duration: o.duration ?? 5000,
        persistent: !!o.persistent,
      };
      setItems(prev => [...prev, n]);
      return n.id;
    };
    window.notifyClear = (id) => setItems(prev => prev.filter(x => x.id !== id));
  }, []);

  const dismiss = (id) => setItems(prev => prev.filter(n => n.id !== id));

  if (items.length === 0) return null;

  return (
    <div style={{
      position: 'fixed', bottom: 20, right: 20,
      display: 'flex', flexDirection: 'column-reverse',
      gap: 8, zIndex: 200,
      pointerEvents: 'none',
      maxWidth: 'calc(100vw - 40px)',
    }}>
      {items.map(n => (
        <Notification key={n.id} n={n} onDismiss={() => dismiss(n.id)} />
      ))}
    </div>
  );
}

function Notification({ n, onDismiss }) {
  const [paused, setPaused] = useStateN(false);
  const [exiting, setExiting] = useStateN(false);
  const timer = useRefN(null);

  const start = () => {
    if (n.persistent) return;
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      setExiting(true);
      setTimeout(onDismiss, 180);
    }, n.duration);
  };

  useEffectN(() => {
    start();
    return () => clearTimeout(timer.current);
  }, []);

  useEffectN(() => {
    if (paused) { clearTimeout(timer.current); }
    else { start(); }
  }, [paused]);

  const dotColor = ({
    success: 'var(--c-success)',
    warning: 'var(--c-warning)',
    danger:  'var(--c-danger)',
    info:    'var(--ink-3)',
  })[n.kind] || 'var(--ink-3)';

  // pulse the dot for non-info states (working, change)
  const pulsing = n.kind !== 'info';

  return (
    <div
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      style={{
        display: 'inline-flex',
        alignItems: 'center', gap: 10,
        padding: n.action ? '6px 8px 6px 14px' : '8px 16px 8px 14px',
        background: 'var(--bg-elev)',
        border: '.5px solid var(--line)',
        borderRadius: 999,
        boxShadow: '0 0 0 .5px rgba(0,0,0,.04), 0 12px 32px rgba(0,0,0,.10)',
        fontSize: 13,
        color: 'var(--ink-2)',
        animation: exiting
          ? 'notif-out .18s var(--ease) both'
          : 'notif-in .26s var(--ease) both',
        pointerEvents: 'auto',
        whiteSpace: 'nowrap',
        maxWidth: '100%',
      }}
    >
      <span style={{
        width: 8, height: 8, borderRadius: '50%',
        background: dotColor, flexShrink: 0,
        animation: pulsing ? 'pulse-dot 1.6s ease-in-out infinite' : 'none',
      }} />
      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{n.text}</span>
      {n.action && (
        <>
          <span style={{ width: 1, height: 14, background: 'var(--line-2)', margin: '0 2px' }} />
          <button
            onClick={() => {
              n.onAction?.();
              setExiting(true);
              setTimeout(onDismiss, 180);
            }}
            style={{
              padding: '4px 10px',
              borderRadius: 999,
              background: 'transparent',
              color: 'var(--ink)',
              fontSize: 12, fontWeight: 500,
              transition: 'background .12s',
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--hover)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >{n.action}</button>
        </>
      )}
    </div>
  );
}

window.NotificationStack = NotificationStack;
