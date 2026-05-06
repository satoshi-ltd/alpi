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

export function NotificationProvider({ children }) {
  const [items, setItems] = useState([]);
  const idRef = useRef(0);
  const timersRef = useRef(new Map());

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
      const id = ++idRef.current;
      const duration = opts.duration ?? 2400;
      setItems((prev) => [
        ...prev,
        {
          id,
          message: opts.message,
          variant: opts.variant ?? "default",
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
