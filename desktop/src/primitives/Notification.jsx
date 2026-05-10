import {
  createContext,
  useCallback,
  useEffect,
  useContext,
  useRef,
  useState,
} from "react";
import styles from "./Notification.module.css";

const NotifyContext = createContext(() => {});

const DEDUP_WINDOW_MS = 2000;

export function NotificationProvider({ children }) {
  const [items, setItems] = useState([]);
  const idRef = useRef(0);
  const timersRef = useRef(new Map());
  // key (message|variant) → last-shown timestamp. Drops repeat toasts
  // within DEDUP_WINDOW_MS so transient failure spam (peer probe ×3,
  // gateway probe ×N) collapses to one visible notification.
  const recentRef = useRef(new Map());

  const dismiss = useCallback((id) => {
    setItems((prev) =>
      prev.map((item) => (item.id === id ? { ...item, status: "exiting" } : item)),
    );
    const timers = timersRef.current;
    if (timers.has(id)) {
      clearTimeout(timers.get(id));
    }
    const timeoutId = setTimeout(() => {
      setItems((prev) => prev.filter((i) => i.id !== id));
      timers.delete(id);
    }, 160);
    timers.set(id, timeoutId);
  }, []);

  const notify = useCallback(
    (opts) => {
      const variant = opts.variant ?? "default";
      const key = `${variant}|${opts.message}`;
      const now = Date.now();
      const recent = recentRef.current;
      const last = recent.get(key) ?? 0;
      if (now - last < DEDUP_WINDOW_MS) return null;
      // Cheap GC of stale entries (any older than the window).
      for (const [k, ts] of recent) {
        if (now - ts >= DEDUP_WINDOW_MS) recent.delete(k);
      }
      recent.set(key, now);

      const id = ++idRef.current;
      const duration = opts.duration ?? 2400;
      setItems((prev) => [
        ...prev,
        {
          id,
          message: opts.message,
          variant,
          status: "entering",
        },
      ]);
      requestAnimationFrame(() => {
        setItems((prev) =>
          prev.map((item) =>
            item.id === id && item.status === "entering"
              ? { ...item, status: "entered" }
              : item,
          ),
        );
      });
      if (duration > 0) {
        const timeoutId = setTimeout(() => dismiss(id), duration);
        timersRef.current.set(id, timeoutId);
      }
      return id;
    },
    [dismiss],
  );

  useEffect(
    () => () => {
      const timers = timersRef.current;
      for (const timeoutId of timers.values()) {
        clearTimeout(timeoutId);
      }
      timers.clear();
    },
    [],
  );

  return (
    <NotifyContext.Provider value={notify}>
      {children}
      <div className={styles.stack} aria-live="polite">
        {items.map((item) => (
          <Toast
            key={item.id}
            variant={item.variant}
            status={item.status}
            onClick={() => dismiss(item.id)}
          >
            {item.message}
          </Toast>
        ))}
      </div>
    </NotifyContext.Provider>
  );
}

export function useNotify() {
  return useContext(NotifyContext);
}

function Toast({ variant, status, children, onClick }) {
  const showDot = variant === "success" || variant === "error";
  return (
    <button
      className={`${styles.toast} ${styles[variant] ?? ""} ${
        styles[status] ?? ""
      }`}
      onClick={onClick}
    >
      {showDot && <span className={styles.dot} aria-hidden />}
      <span className={styles.message}>{children}</span>
    </button>
  );
}
