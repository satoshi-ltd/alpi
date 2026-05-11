import { useEffect, useMemo, useRef, useState } from "react";
import Kbd from "./Kbd.jsx";
import styles from "./CommandPalette.module.css";

export default function CommandPalette({ open, onClose, commands }) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef(null);
  const listRef = useRef(null);

  useEffect(() => {
    if (open) {
      setQuery("");
      setSelectedIndex(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter((c) => c.label.toLowerCase().includes(q));
  }, [query, commands]);

  const grouped = useMemo(() => {
    const map = new Map();
    filtered.forEach((c) => {
      const g = c.group ?? "Other";
      if (!map.has(g)) map.set(g, []);
      map.get(g).push(c);
    });
    return Array.from(map.entries());
  }, [filtered]);

  useEffect(() => {
    if (selectedIndex >= filtered.length) setSelectedIndex(0);
  }, [filtered.length, selectedIndex]);

  useEffect(() => {
    const el = listRef.current?.querySelector(`[data-idx='${selectedIndex}']`);
    el?.scrollIntoView({ block: "nearest" });
  }, [selectedIndex]);

  function execute(cmd) {
    onClose?.();
    cmd?.action?.();
  }

  function onKeyDown(e) {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose?.();
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) =>
        filtered.length === 0 ? 0 : (i + 1) % filtered.length,
      );
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) =>
        filtered.length === 0 ? 0 : (i - 1 + filtered.length) % filtered.length,
      );
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      const cmd = filtered[selectedIndex];
      if (cmd) execute(cmd);
    }
  }

  if (!open) return null;

  let flatIdx = -1;
  return (
    <div
      className={styles.backdrop}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose?.();
      }}
    >
      <div className={styles.panel} role="dialog" aria-label="Command palette">
        <input
          ref={inputRef}
          className={styles.input}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setSelectedIndex(0);
          }}
          onKeyDown={onKeyDown}
          placeholder="Type a command…"
          spellCheck={false}
          autoCapitalize="off"
        />
        <div ref={listRef} className={styles.list}>
          {filtered.length === 0 && (
            <div className={styles.empty}>No matches</div>
          )}
          {grouped.map(([group, items]) => (
            <div key={group} className={styles.group}>
              <div className={styles.groupLabel}>{group}</div>
              {items.map((cmd) => {
                flatIdx += 1;
                const idx = flatIdx;
                const active = idx === selectedIndex;
                return (
                  <button
                    key={cmd.id}
                    type="button"
                    data-idx={idx}
                    className={`${styles.row} ${active ? styles.rowActive : ""}`}
                    onMouseEnter={() => setSelectedIndex(idx)}
                    onClick={() => execute(cmd)}
                  >
                    <span className={styles.label}>{cmd.label}</span>
                    {cmd.hint && (
                      <span className={styles.hint}>
                        <Kbd>{cmd.hint}</Kbd>
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
