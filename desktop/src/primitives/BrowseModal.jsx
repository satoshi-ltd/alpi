import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { IconBtn, Mono, RefreshBar, SearchIcon, Tip, XIcon } from "./index.js";
import styles from "./BrowseModal.module.css";

export { styles as browseStyles };

export default function BrowseModal({
  open,
  onClose,
  title,
  count,
  kicker,
  actions,
  search,
  list,
  loading = false,
  loadingLabel = "Loading",
  accent = null,
  children,
}) {
  const wrapRef = useRef(null);
  const searchRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === "Escape") { e.preventDefault(); onClose?.(); return; }
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        const active = document.activeElement;
        if (active !== searchRef.current && active?.getAttribute?.("role") !== "option") return;
        const opts = Array.from(wrapRef.current?.querySelectorAll('[role="option"]') || [])
          .filter((el) => el.tagName === "BUTTON" || el.tabIndex >= 0);
        if (!opts.length) return;
        e.preventDefault();
        const idx = opts.indexOf(active);
        const step = e.key === "ArrowDown" ? 1 : -1;
        const next = idx === -1
          ? (step === 1 ? opts[0] : opts[opts.length - 1])
          : opts[Math.min(opts.length - 1, Math.max(0, idx + step))];
        next?.focus();
      }
    };
    const onClick = (e) => { if (wrapRef.current && !wrapRef.current.contains(e.target)) onClose?.(); };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open, onClose]);

  useEffect(() => {
    if (open) searchRef.current?.focus();
  }, [open]);

  if (!open) return null;

  return createPortal(
    <div className={`anim-overlay ${styles.backdrop}`}>
      <div ref={wrapRef} className={`anim-dialog ${styles.modal}`} role="dialog" aria-modal="true" aria-label={title}>
        <header className={styles.header}>
          <span className={styles.headerLead}>
            <span className={styles.title}>{title}</span>
            {count != null ? <span className={styles.count}>{count}</span> : null}
          </span>
          {kicker ? <Mono className={styles.kicker}>· {kicker}</Mono> : null}
          <span className={styles.headerSpacer} />
          {actions}
          <Tip text="Close" side="down">
            <IconBtn aria-label="Close" onClick={() => onClose?.()}><XIcon /></IconBtn>
          </Tip>
        </header>
        <div className={styles.syncSlot}>
          <RefreshBar active={loading} accent={accent} controlled label={loadingLabel} />
        </div>

        <div className={styles.body}>
          <div className={styles.sidebar}>
            {search ? (
              <div className={styles.searchWrap}>
                <SearchIcon className={styles.searchIcon} />
                <input
                  ref={searchRef}
                  type="text"
                  className={styles.searchInput}
                  placeholder={search.placeholder}
                  value={search.value}
                  onChange={(e) => search.onChange(e.target.value)}
                  aria-label={search.label || search.placeholder}
                />
                {search.value ? (
                  <IconBtn aria-label="Clear search" tip="Clear search" onClick={() => search.onChange("")}><XIcon /></IconBtn>
                ) : null}
              </div>
            ) : null}
            {list}
          </div>
          <div className={styles.detail}>{children}</div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
