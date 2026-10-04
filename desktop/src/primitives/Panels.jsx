import Button from "./Button.jsx";
import ConfirmDelete from "./ConfirmDelete.jsx";
import Icon from "./Icon.jsx";
import IconBtn from "./IconBtn.jsx";
import { OverlayScope, useOverlay } from "../hooks/useOverlay.js";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { I } from "./icons.jsx";
import KeyHint from "./KeyHint.jsx";
import { fuzzyMatch, splitByRanges } from "../lib/fuzzy.js";
import { canSelfUpdate, updateHint } from "../../../common/updateHint.mjs";
import styles from "./Panels.module.css";
import ConnectElsewhere from "./ConnectElsewhere.jsx";

export function Scrim({ onClose, children, align = "flex-start", top = 96, dismissable = true }) {
  const ref = useRef(null);
  const isTop = useOverlay({ open: true, onClose: dismissable ? onClose : undefined, ref, modal: true });
  return createPortal(
    <OverlayScope overlay={isTop}>
      <div
        ref={ref}
        tabIndex={-1}
        className={`anim-fade ${styles.scrim}`}
        onClick={(e) => {
          if (isTop() && dismissable && e.target === e.currentTarget) onClose();
        }}
        style={{
          alignItems: align,
          padding: `${top}px 60px 60px`,
        }}
      >
        {children}
      </div>
    </OverlayScope>,
    document.body,
  );
}

export function PanelShell({ children, width = 880, maxHeight = "70vh" }) {
  return (
    <div className={`anim-pop ${styles.shell}`} style={{ width, maxHeight }}>
      {children}
    </div>
  );
}

export function ConnectionPanel({
  open,
  onClose,
  connections = [],
  activeId,
  onPick,
  onForget,
  onRename,
  onPair,
  locked = false,
}) {
  const [renaming, setRenaming] = useState(null);
  const [forgetFor, setForgetFor] = useState(null);
  const renameCancelled = useRef(false);
  function beginRename(r) {
    renameCancelled.current = false;
    setRenaming({ id: r.id, value: r.name });
  }
  function cancelRename(e) {
    e.preventDefault();
    e.stopPropagation();
    // Escape blurs the field next; the blur must not commit what Escape just discarded.
    renameCancelled.current = true;
    setRenaming(null);
  }
  async function commitRename(r) {
    if (renameCancelled.current) {
      renameCancelled.current = false;
      return;
    }
    const name = (renaming?.value ?? "").trim();
    setRenaming(null);
    if (!name || name === r.name) return;
    await onRename?.(r, name);
  }
  if (!open) return null;
  return (
    <Scrim onClose={onClose} top={80} dismissable={!locked}>
      <PanelShell width={560} maxHeight="auto">
        <div className={`row between ${styles.panelHeader}`}>
          <div className={`row row-gap ${styles.headerRow}`}>
            <I.Globe />
            <span className={styles.panelTitle}>Connection</span>
            <span className={`eyebrow ${styles.headerEyebrow}`}>
              {locked ? "No host yet. Add a connection to continue." : "where alpi runs"}
            </span>
          </div>
          {!locked && (
            <IconBtn tip="Close" tipSide="r" onClick={onClose}>
              <I.X />
            </IconBtn>
          )}
        </div>

        <div className={`col ${styles.connList}`}>
          {connections.map((r) => {
            const active = activeId === r.id;
            const dotColor = r.revoked
              ? "var(--c-warning)"
              : r.status === "connected" || r.status === "online"
                ? "var(--c-success)"
                : r.status === "offline"
                  ? "var(--c-danger)"
                  : r.status === "disabled"
                    ? "var(--ink-3)"
                  : "var(--c-warning)";
            const isLocal = r.kind === "local" || r.isLocal;
            return (
              <div
                key={r.id}
                role="button"
                tabIndex={0}
                onClick={() => onPick?.(r)}
                onKeyDown={(e) => {
                  if (e.target !== e.currentTarget) return;
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onPick?.(r);
                  }
                }}
                className={`row row-gap ${styles.connRow} ${active ? styles.connRowActive : ""}`}
              >
                <span className={styles.connIcon}>
                  {isLocal ? <I.Cpu /> : <I.Server />}
                  <span
                    className={styles.connDot}
                    style={{ background: dotColor }}
                  />
                </span>
                <div className={`col ${styles.connBody}`}>
                  <div className={`row row-gap ${styles.connBodyTop}`}>
                    {renaming?.id === r.id ? (
                      <input
                        autoFocus
                        aria-label="Connection name"
                        className={styles.renameInput}
                        value={renaming.value}
                        maxLength={64}
                        onClick={(e) => { e.preventDefault(); e.stopPropagation(); }}
                        onDoubleClick={(e) => { e.preventDefault(); e.stopPropagation(); }}
                        onMouseDown={(e) => e.stopPropagation()}
                        onChange={(e) => setRenaming({ id: r.id, value: e.target.value })}
                        onBlur={() => commitRename(r)}
                        onKeyDown={(e) => {
                          e.stopPropagation();
                          if (e.key === "Enter") commitRename(r);
                          if (e.key === "Escape") cancelRename(e);
                        }}
                      />
                    ) : (
                      <span className={styles.connName}>{r.name}</span>
                    )}
                    {active && <span className="tag">current</span>}
                    {r.status === "offline" && (
                      <span className={`tag ${styles.tagOffline}`}>
                        offline
                      </span>
                    )}
                    {r.status === "disabled" && <span className="tag">disabled</span>}
                    {r.revoked && (
                      <span className={`tag ${styles.tagOffline}`}>revoked</span>
                    )}
                    {r.update_available && (
                      <span
                        className={`tag ${styles.tagUpdate}`}
                        title={canSelfUpdate(r.self_update) ? undefined : updateHint(r.installer, r.update_available)}
                      >
                        update
                      </span>
                    )}
                  </div>
                  <span className={`mono ${styles.connHost}`}>
                    {r.host}
                    {r.alpi_version && (
                      <span className={styles.connVersion}>
                        {" · v"}
                        {r.alpi_version}
                      </span>
                    )}
                  </span>
                </div>
                {!isLocal && (
                  <span
                    className={`${styles.rowActions} ${forgetFor === r.id ? styles.rowActionsOpen : ""}`}
                    onClick={(e) => e.stopPropagation()}
                  >
                    {onRename && (
                      <IconBtn tip="Rename" tipSide="up" onClick={() => beginRename(r)}>
                        <Icon name="pencil" />
                      </IconBtn>
                    )}
                    <span className={styles.confirmAction}>
                      <IconBtn
                        tip="Forget"
                        tipSide="up"
                        className={styles.dangerAction}
                        onClick={() => setForgetFor((cur) => (cur === r.id ? null : r.id))}
                      >
                        <Icon name="x" />
                      </IconBtn>
                      <ConfirmDelete
                        open={forgetFor === r.id}
                        title={`Forget ${r.name}?`}
                        consequence="Only this computer forgets it. The host still lists the device until an admin removes it there."
                        confirmLabel="Forget connection"
                        onClose={() => setForgetFor(null)}
                        onConfirm={() => onForget?.(r)}
                      />
                    </span>
                  </span>
                )}
              </div>
            );
          })}
        </div>

        <div className={styles.pairFoot}>
          <div className={`row between ${styles.pairFootHead}`}>
            <span className="eyebrow">Connect to another computer</span>
            <span className={styles.pairFootHint}>
              Paste an{" "}
              <code className={`mono ${styles.pairCode}`}>alpi://</code> link
              from another machine
            </span>
          </div>
          <ConnectElsewhere onConnect={async (link) => { await onPair?.(link); }} />
        </div>
      </PanelShell>
    </Scrim>
  );
}

export function paletteRows(groups, query) {
  const q = query.trim();
  const out = [];
  const ordered = q ? groups : [...groups.filter((g) => g.leadWhenIdle), ...groups.filter((g) => !g.leadWhenIdle)];
  for (const g of ordered) {
    const idle = !q && g.idle;
    if (g.searchOnly && !q && !idle) continue;
    let items = g.items.map((it) => {
      if (!q) return { ...it, ranges: [], score: 0 };
      const hit = fuzzyMatch(it.label, q);
      if (hit) return { ...it, ranges: hit.ranges, score: hit.score };
      const extra = (it.keywords || []).map((k) => fuzzyMatch(k, q)).filter(Boolean);
      if (!extra.length) return null;
      return { ...it, ranges: [], score: Math.max(...extra.map((x) => x.score)) - 400 };
    }).filter(Boolean);
    if (q) items.sort((a, b) => b.score - a.score);
    const limit = idle ? idle.limit : g.limit;
    if (limit) items = items.slice(0, limit);
    if (!items.length) continue;
    out.push({ kind: "header", label: idle ? idle.label : g.label });
    for (const it of items) out.push({ kind: "item", ...it });
  }
  return out;
}

function Highlighted({ text, ranges }) {
  return splitByRanges(text, ranges).map((part, i) =>
    part.hit ? <mark key={i} className={styles.paletteHit}>{part.text}</mark> : part.text,
  );
}

export function Palette({ open, onClose, groups = [], placeholder = "Search profiles, sessions and commands…" }) {
  const [q, setQ] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const inputRef = useRef(null);
  const baseId = useId();

  useEffect(() => {
    if (open) {
      setQ("");
      setSelectedId(null);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  const flat = useMemo(() => paletteRows(groups, q), [q, groups]);
  const actionableItems = useMemo(() => flat.filter((x) => x.kind === "item" && x.onSelect), [flat]);
  const found = selectedId == null ? -1 : actionableItems.findIndex((it) => it.id === selectedId);
  const idx = found >= 0 ? found : 0;
  const setIdx = (next) => {
    const i = typeof next === "function" ? next(idx) : next;
    setSelectedId(actionableItems[i]?.id ?? null);
  };
  const optionId = (i) => `${baseId}-opt-${i}`;
  const activeId = actionableItems[idx] ? optionId(idx) : undefined;

  useEffect(() => {
    if (!open || !activeId) return;
    const el = document.getElementById(activeId);
    if (el && typeof el.scrollIntoView === "function") el.scrollIntoView({ block: "nearest" });
  }, [open, activeId]);

  function run(it) {
    if (!it?.onSelect) return;
    it.onSelect?.();
    onClose?.();
  }

  function onKey(e) {
    if (e.key === "ArrowDown" || (!e.shiftKey && e.key === "Tab")) {
      e.preventDefault();
      setIdx((i) => Math.min(actionableItems.length - 1, i + 1));
    } else if (e.key === "ArrowUp" || (e.shiftKey && e.key === "Tab")) {
      e.preventDefault();
      setIdx((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      run(actionableItems[idx]);
    }
  }

  if (!open) return null;
  const listId = `${baseId}-list`;
  return (
    <Scrim onClose={onClose} top={120}>
      <PanelShell width={560} maxHeight="60vh">
        <div className={styles.paletteInputWrap}>
          <I.Search className={styles.paletteSearchIcon} />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setSelectedId(null);
            }}
            onKeyDown={onKey}
            placeholder={placeholder}
            className={styles.paletteInput}
            role="combobox"
            aria-expanded="true"
            aria-controls={listId}
            aria-activedescendant={activeId}
            aria-autocomplete="list"
            aria-label="Command palette"
          />
        </div>
        <div id={listId} role="listbox" aria-label="Results" className={`scroll ${styles.paletteBody}`}>
          {flat.length === 0 ? (
            <div className={`col center ${styles.paletteEmpty}`}>
              No matches
            </div>
          ) : (
            flat.map((row) => {
              if (row.kind === "header") {
                return (
                  <div
                    key={`h-${row.label}`}
                    role="presentation"
                    className={`eyebrow ${styles.paletteHeader}`}
                  >
                    {row.label}
                  </div>
                );
              }
              const itemIndex = actionableItems.findIndex((it) => it.id === row.id);
              const selected = itemIndex >= 0 && itemIndex === idx;
              const actionable = Boolean(row.onSelect);
              return (
                <div
                  key={row.id}
                  id={itemIndex >= 0 ? optionId(itemIndex) : undefined}
                  role="option"
                  aria-selected={selected}
                  aria-disabled={!actionable || undefined}
                  onClick={() => run(row)}
                  onMouseMove={() => {
                    if (itemIndex >= 0 && itemIndex !== idx) setIdx(itemIndex);
                  }}
                  className={`row ${styles.paletteItem} ${selected ? styles.paletteItemSelected : ""} ${actionable ? "" : styles.paletteItemStatic}`}
                >
                  <span className={styles.paletteGlyph}>
                    {row.glyph || <I.ChevRight />}
                  </span>
                  <span className={styles.paletteLabel}>
                    <Highlighted text={row.label} ranges={row.ranges} />
                  </span>
                  {row.sub ? <span className={styles.paletteSub}>{row.sub}</span> : null}
                  <span className={styles.paletteSpacer} />
                  <KeyHint hint={row.shortcut} />
                </div>
              );
            })
          )}
        </div>
      </PanelShell>
    </Scrim>
  );
}
