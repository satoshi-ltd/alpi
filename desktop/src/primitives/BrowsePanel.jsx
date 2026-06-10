import { useEffect, useMemo, useRef, useState } from "react";
import { IconBtn, Tip, XIcon, Eyebrow } from "./index.js";
import styles from "./BrowsePanel.module.css";

export default function BrowsePanel({
  open,
  onClose,
  title,
  kicker,
  items,
  categoryOrder,
  alwaysShowGroups = false,
  emptyText = "Nothing to show",
  renderDetail,
}) {
  const [query, setQuery] = useState("");
  const [selectedKey, setSelectedKey] = useState(null);
  const inputRef = useRef(null);
  const listRef = useRef(null);

  useEffect(() => {
    if (open) {
      setQuery("");
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((it) => {
      const haystack = `${it.name} ${it.description || ""} ${it.category || ""}`;
      return haystack.toLowerCase().includes(q);
    });
  }, [query, items]);

  const grouped = useMemo(() => {
    const map = new Map();
    for (const it of filtered) {
      const cat = it.category || "Other";
      if (!map.has(cat)) map.set(cat, []);
      map.get(cat).push(it);
    }
    for (const list of map.values()) {
      list.sort((a, b) => a.name.localeCompare(b.name));
    }
    const order = categoryOrder || [];
    const ordered = [];
    for (const cat of order) {
      if (map.has(cat)) ordered.push([cat, map.get(cat)]);
    }
    for (const [cat, list] of map.entries()) {
      if (!order.includes(cat)) ordered.push([cat, list]);
    }
    return ordered;
  }, [filtered, categoryOrder]);

  const flat = useMemo(
    () => grouped.flatMap(([, list]) => list),
    [grouped],
  );

  useEffect(() => {
    if (flat.length === 0) {
      setSelectedKey(null);
      return;
    }
    if (!flat.some((it) => keyOf(it) === selectedKey)) {
      setSelectedKey(keyOf(flat[0]));
    }
  }, [flat, selectedKey]);

  useEffect(() => {
    if (!selectedKey) return;
    const el = listRef.current?.querySelector(`[data-key='${cssEscape(selectedKey)}']`);
    el?.scrollIntoView({ block: "nearest" });
  }, [selectedKey]);

  function onKeyDown(e) {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose?.();
      return;
    }
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (flat.length === 0) return;
      const idx = flat.findIndex((it) => keyOf(it) === selectedKey);
      const delta = e.key === "ArrowDown" ? 1 : -1;
      const next = (idx + delta + flat.length) % flat.length;
      setSelectedKey(keyOf(flat[next]));
    }
  }

  if (!open) return null;

  const current = flat.find((it) => keyOf(it) === selectedKey) || null;
  const total = items.length;
  const showing = flat.length;
  const counter = total === showing ? `${total}` : `${showing} of ${total}`;

  return (
    <div
      className={`anim-overlay ${styles.backdrop}`}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose?.();
      }}
    >
      <div className={`anim-pop ${styles.panel}`} role="dialog" aria-label={title}>
        <div className={styles.header}>
          <span className={styles.title}>{title}</span>
          <span className={styles.counter}>{counter}</span>
          {kicker && <Eyebrow className={styles.kicker}>{kicker}</Eyebrow>}
          <span style={{ flex: 1 }} />
          <Tip text="Close" side="r">
            <IconBtn onClick={() => onClose?.()} aria-label="Close">
              <XIcon />
            </IconBtn>
          </Tip>
        </div>
        <div className={styles.body}>
          <div className={styles.side}>
            <div className={styles.inputWrap}>
              <input
                ref={inputRef}
                className={styles.input}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder={`Search ${title.toLowerCase()}…`}
                spellCheck={false}
                autoCapitalize="off"
              />
            </div>
            <div ref={listRef} className={styles.list}>
              {flat.length === 0 ? (
                <div className={styles.empty}>{emptyText}</div>
              ) : (
                grouped.map(([cat, list]) => (
                  <div key={cat} className={styles.group}>
                    {(alwaysShowGroups || grouped.length > 1) && (
                      <Eyebrow as="div" className={styles.groupLabel}>{cat}</Eyebrow>
                    )}
                    {list.map((it) => {
                      const k = keyOf(it);
                      const active = k === selectedKey;
                      const cls = [
                        styles.row,
                        active ? styles.rowActive : "",
                        it.muted ? styles.rowMuted : "",
                      ].filter(Boolean).join(" ");
                      return (
                        <button
                          key={k}
                          type="button"
                          data-key={k}
                          className={cls}
                          onClick={() => setSelectedKey(k)}
                        >
                          <span className={styles.rowName}>{it.name}</span>
                          {it.tag && <span className={styles.rowTag}>{it.tag}</span>}
                        </button>
                      );
                    })}
                  </div>
                ))
              )}
            </div>
          </div>
          <div className={styles.detail}>
            {current && renderDetail ? (
              renderDetail(current)
            ) : (
              <div className={styles.detailEmpty}>
                {flat.length === 0 ? emptyText : "Select an item"}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function keyOf(it) {
  return `${it.category || "_"}::${it.name}`;
}

function cssEscape(s) {
  return s.replace(/[^a-zA-Z0-9_-]/g, (c) => `\\${c}`);
}
