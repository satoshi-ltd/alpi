import { OverlayScope, useOverlay } from "../hooks/useOverlay.js";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef } from "react";
import { createPortal } from "react-dom";
import { IconBtn, Mono, RefreshBar, SearchIcon, Tip, XIcon } from "./index.js";
import Crease from "./Crease.jsx";
import Fold from "./Fold.jsx";
import styles from "./BrowseModal.module.css";

export { styles as browseStyles };

const ShellContext = createContext(null);

export function BrowseShell({ open, onClose, label, guardRef: sharedGuard = null, children }) {
  const wrapRef = useRef(null);
  const ownGuard = useRef(null);
  const guardRef = sharedGuard ?? ownGuard;
  const close = useCallback(() => {
    if (guardRef.current && !guardRef.current()) return;
    onClose?.();
  }, [onClose]);
  const isTop = useOverlay({ open, onClose: close, ref: wrapRef, modal: true });
  const shell = useMemo(() => ({ close, guardRef }), [close, guardRef]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (!isTop()) return;
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        const active = document.activeElement;
        const option = active?.closest?.('[role="option"]') ?? null;
        const adrift = active === wrapRef.current || active === document.body || !active;
        const inSearch = !!active?.matches?.("[data-browse-search]");
        if (!inSearch && !option && !adrift) return;
        const opts = Array.from(wrapRef.current?.querySelectorAll('[role="option"]') || [])
          .filter((el) => el.tagName === "BUTTON" || el.tabIndex >= 0);
        if (!opts.length) return;
        e.preventDefault();
        const idx = opts.indexOf(option);
        const step = e.key === "ArrowDown" ? 1 : -1;
        const next = idx === -1
          ? (step === 1 ? opts[0] : opts[opts.length - 1])
          : opts[Math.min(opts.length - 1, Math.max(0, idx + step))];
        next?.focus();
      }
    };
    const onClick = (e) => { if (isTop() && wrapRef.current && !wrapRef.current.contains(e.target)) close(); };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open, close]);

  if (!open) return null;

  return createPortal(
    <OverlayScope overlay={isTop}>
      <div className={`anim-overlay ${styles.backdrop}`}>
        <div ref={wrapRef} tabIndex={-1} className={`anim-dialog ${styles.modal}`} role="dialog" aria-modal="true" aria-label={label}>
          <ShellContext.Provider value={shell}>{children}</ShellContext.Provider>
        </div>
      </div>
    </OverlayScope>,
    document.body,
  );
}

export function useBrowseCloseGuard(guard) {
  const shell = useContext(ShellContext);
  useEffect(() => {
    if (!shell) return undefined;
    shell.guardRef.current = guard;
    return () => {
      if (shell.guardRef.current === guard) shell.guardRef.current = null;
    };
  }, [shell, guard]);
}

export function BrowseBody({
  title,
  count,
  kicker,
  actions,
  search,
  list,
  loading = false,
  loadingLabel = "Loading",
  accent = null,
  owner = null,
  sections = null,
  section = null,
  onSection = null,
  children,
}) {
  const shell = useContext(ShellContext);
  const searchRef = useRef(null);

  useEffect(() => {
    searchRef.current?.focus();
  }, []);

  const switchTo = (id) => {
    if (shell?.guardRef.current && !shell.guardRef.current()) return;
    onSection?.(id);
  };

  return (
    <>
      <header className={styles.header}>
        {owner ? (
          <>
            <span className={styles.owner}>
              <Fold fold={owner.fold} color={owner.accent} size={18} />
              {owner.accent ? <Crease text={owner.name} accent={owner.accent} size={17} /> : <span className={styles.ownerName}>{owner.name}</span>}
            </span>
            {sections ? (
              <span className={styles.sections} role="tablist" aria-label={`${owner.name} panels`}>
                {sections.map((s) => {
                  const on = s.id === section;
                  return (
                    <button
                      key={s.id}
                      type="button"
                      role="tab"
                      aria-selected={on}
                      className={`${styles.section} ${on ? styles.sectionOn : ""}`.trim()}
                      onClick={() => !on && switchTo(s.id)}
                    >
                      {s.label}
                      {on && count != null ? <span className={styles.count}>{count}</span> : null}
                    </button>
                  );
                })}
              </span>
            ) : null}
          </>
        ) : (
          <>
            <span className={styles.headerLead}>
              <span className={styles.title}>{title}</span>
              {count != null ? <span className={styles.count}>{count}</span> : null}
            </span>
            {kicker ? <Mono className={styles.kicker}>· {kicker}</Mono> : null}
          </>
        )}
        <span className={styles.headerSpacer} />
        {actions}
        <Tip text="Close" side="down">
          <IconBtn aria-label="Close" onClick={() => shell?.close()}><XIcon /></IconBtn>
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
                data-browse-search=""
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
    </>
  );
}

export default function BrowseModal({ open, onClose, title, ...body }) {
  return (
    <BrowseShell open={open} onClose={onClose} label={title}>
      <BrowseBody title={title} {...body} />
    </BrowseShell>
  );
}
