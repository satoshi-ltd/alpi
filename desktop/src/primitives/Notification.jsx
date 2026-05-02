import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import styles from "./Notification.module.css";

const NotifyContext = createContext(() => {});

export function NotificationProvider({ children }) {
  const [items, setItems] = useState([]);
  const idRef = useRef(0);

  const dismiss = useCallback((id) => {
    setItems((prev) => prev.filter((i) => i.id !== id));
  }, []);

  const notify = useCallback(
    (opts) => {
      const id = ++idRef.current;
      const duration = opts.duration ?? 2400;
      setItems((prev) => [
        ...prev,
        { id, message: opts.message, variant: opts.variant ?? "default" },
      ]);
      if (duration > 0) {
        setTimeout(() => dismiss(id), duration);
      }
      return id;
    },
    [dismiss],
  );

  return (
    <NotifyContext.Provider value={notify}>
      {children}
      <div className={styles.stack} aria-live="polite">
        {items.map((item) => (
          <Toast
            key={item.id}
            variant={item.variant}
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

function Toast({ variant, children, onClick }) {
  const [entered, setEntered] = useState(false);
  useEffect(() => {
    const id = requestAnimationFrame(() => setEntered(true));
    return () => cancelAnimationFrame(id);
  }, []);
  const showDot = variant === "success" || variant === "error";
  return (
    <button
      className={`${styles.toast} ${styles[variant] ?? ""} ${
        entered ? styles.entered : ""
      }`}
      onClick={onClick}
    >
      {showDot && <span className={styles.dot} aria-hidden />}
      <span className={styles.message}>{children}</span>
    </button>
  );
}
