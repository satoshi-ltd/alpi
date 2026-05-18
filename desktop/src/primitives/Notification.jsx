import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import styles from "./Notification.module.css";

const NotifyContext = createContext(null);

const DEDUP_WINDOW_MS = 2000;

function normalize(arg, extra) {
  const o = typeof arg === "string" ? { text: arg, ...(extra || {}) } : arg || {};
  const text = o.text ?? o.message ?? "";
  let kind = o.kind;
  if (!kind) {
    const v = o.variant;
    if (v === "error") kind = "danger";
    else if (v === "success") kind = "success";
    else if (v === "warning") kind = "warning";
    else kind = "info";
  }
  return {
    text,
    kind,
    action: o.action,
    onAction: o.onAction,
    duration: o.duration ?? 5000,
    persistent: !!o.persistent,
  };
}

export function NotificationProvider({ children }) {
  const [items, setItems] = useState([]);
  const recentRef = useRef(new Map());

  const dismiss = useCallback((id) => {
    setItems((prev) => prev.filter((x) => x.id !== id));
  }, []);

  const notify = useCallback((arg, extra) => {
    const o = normalize(arg, extra);
    if (!o.text) return null;
    const key = `${o.kind}|${o.text}`;
    const now = Date.now();
    const recent = recentRef.current;
    const last = recent.get(key) ?? 0;
    if (now - last < DEDUP_WINDOW_MS) return null;
    for (const [k, ts] of recent) {
      if (now - ts >= DEDUP_WINDOW_MS) recent.delete(k);
    }
    recent.set(key, now);
    const id = Math.random().toString(36).slice(2, 9);
    setItems((prev) => [...prev, { id, ...o }]);
    return id;
  }, []);

  useEffect(() => {
    window.notify = notify;
    window.notifyClear = dismiss;
    return () => {
      if (window.notify === notify) delete window.notify;
      if (window.notifyClear === dismiss) delete window.notifyClear;
    };
  }, [notify, dismiss]);

  return (
    <NotifyContext.Provider value={notify}>
      {children}
      <NotificationStack items={items} onDismiss={dismiss} />
    </NotifyContext.Provider>
  );
}

export function useNotify() {
  return useContext(NotifyContext) ?? (() => null);
}

function NotificationStack({ items, onDismiss }) {
  if (items.length === 0) return null;
  return (
    <div className={styles.stack} aria-live="polite">
      {items.map((n) => (
        <Notification key={n.id} n={n} onDismiss={() => onDismiss(n.id)} />
      ))}
    </div>
  );
}

function Notification({ n, onDismiss }) {
  const [paused, setPaused] = useState(false);
  const [exiting, setExiting] = useState(false);
  const timer = useRef(null);

  const start = useCallback(() => {
    if (n.persistent) return;
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      setExiting(true);
      setTimeout(onDismiss, 180);
    }, n.duration);
  }, [n.persistent, n.duration, onDismiss]);

  useEffect(() => {
    start();
    return () => clearTimeout(timer.current);
  }, [start]);

  useEffect(() => {
    if (paused) clearTimeout(timer.current);
    else start();
  }, [paused, start]);

  const dotColor =
    {
      success: "var(--c-success)",
      warning: "var(--c-warning)",
      danger: "var(--c-danger)",
      info: "var(--ink-3)",
    }[n.kind] || "var(--ink-3)";
  const pulsing = n.kind !== "info";

  return (
    <div
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      className={`${styles.toast} ${n.action ? styles.toastWithAction : ""}`}
      style={{
        animation: exiting
          ? "ds-notif-out .18s var(--ease) both"
          : "ds-notif-in .26s var(--ease) both",
      }}
    >
      <span
        className={`${styles.dot} ${pulsing ? styles.dotPulse : ""}`}
        style={{ background: dotColor }}
      />
      <span className={styles.text}>{n.text}</span>
      {n.action && (
        <>
          <span aria-hidden className={styles.divider} />
          <button
            type="button"
            onClick={() => {
              n.onAction?.();
              setExiting(true);
              setTimeout(onDismiss, 180);
            }}
            className={styles.actionBtn}
          >
            {n.action}
          </button>
        </>
      )}
    </div>
  );
}
