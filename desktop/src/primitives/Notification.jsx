import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { plainError } from "../../../common/plainError.mjs";
import styles from "./Notification.module.css";

const NotifyContext = createContext(null);

const DEDUP_WINDOW_MS = 2000;
const MAX_TOASTS = 3;

function normalize(arg, extra) {
  const o = typeof arg === "string" ? { text: arg, ...(extra || {}) } : arg || {};
  let text = o.text ?? o.message ?? "";
  let kind = o.kind;
  if (!kind) {
    const v = o.variant;
    if (v === "error") kind = "danger";
    else if (v === "success") kind = "success";
    else if (v === "warning") kind = "warning";
    else kind = "info";
  }
  if (kind === "danger" || o.variant === "danger") text = plainError(text);
  return {
    text,
    kind,
    action: o.action,
    onAction: o.onAction,
    onPause: o.onPause,
    onResume: o.onResume,
    duration: o.duration ?? 5000,
    persistent: !!o.persistent,
  };
}

function capStack(items) {
  let over = items.length - MAX_TOASTS;
  if (over <= 0) return items;
  return items.filter((x) => x.pinned || over-- <= 0);
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
    const pinned = typeof arg === "object" && arg ? arg.id : undefined;
    if (pinned) {
      setItems((prev) => {
        const at = prev.findIndex((x) => x.id === pinned);
        if (at < 0) return capStack([...prev, { id: pinned, rev: 0, pinned: true, ...o }]);
        const next = prev.slice();
        next[at] = { ...next[at], ...o, rev: next[at].rev + 1 };
        return next;
      });
      return pinned;
    }
    const key = `${o.kind}|${o.text}`;
    const now = Date.now();
    const recent = recentRef.current;
    const last = recent.get(key) ?? 0;
    if (!o.onAction && now - last < DEDUP_WINDOW_MS) return null;
    for (const [k, ts] of recent) {
      if (now - ts >= DEDUP_WINDOW_MS) recent.delete(k);
    }
    recent.set(key, now);
    const id = Math.random().toString(36).slice(2, 9);
    setItems((prev) => capStack([...prev, { id, rev: 0, ...o }]));
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

const NOOP_NOTIFY = () => null;

export function useNotify() {
  return useContext(NotifyContext) ?? NOOP_NOTIFY;
}

function NotificationStack({ items, onDismiss }) {
  if (items.length === 0) return null;
  return (
    <div className={styles.stack} aria-live="polite">
      {items.map((n) => (
        <Notification key={n.id} n={n} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

function Notification({ n, onDismiss }) {
  const [paused, setPaused] = useState(false);
  const [exiting, setExiting] = useState(false);
  const timer = useRef(null);
  const exitTimer = useRef(null);
  const pausedRef = useRef(false);
  const latest = useRef(n);
  latest.current = n;

  // Stable, or every render of the stack would restart this toast's window while the delete it offers to undo runs on.
  const close = useCallback(() => onDismiss(n.id), [onDismiss, n.id]);

  const beginExit = useCallback(() => {
    clearTimeout(exitTimer.current);
    setExiting(true);
    exitTimer.current = setTimeout(close, 180);
  }, [close]);

  const start = useCallback(() => {
    if (n.persistent) return;
    clearTimeout(timer.current);
    timer.current = setTimeout(beginExit, n.duration);
  }, [n.persistent, n.duration, beginExit]);

  useEffect(() => {
    clearTimeout(exitTimer.current);
    setExiting(false);
    if (pausedRef.current) latest.current.onPause?.();
  }, [n.rev]);

  useEffect(() => {
    if (!paused) start();
    return () => clearTimeout(timer.current);
  }, [paused, start, n.rev]);

  // A toast retired while hovered never gets mouseleave; its owner must still hear the resume.
  useEffect(() => () => {
    clearTimeout(exitTimer.current);
    if (pausedRef.current) latest.current.onResume?.();
  }, []);

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
      onMouseEnter={() => {
        pausedRef.current = true;
        setPaused(true);
        n.onPause?.();
      }}
      onMouseLeave={() => {
        pausedRef.current = false;
        setPaused(false);
        n.onResume?.();
      }}
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
              beginExit();
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
