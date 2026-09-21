import Button from "./Button.jsx";
import ConfirmDelete from "./ConfirmDelete.jsx";
import Icon from "./Icon.jsx";
import IconBtn from "./IconBtn.jsx";
import { OverlayScope, useOverlay } from "../hooks/useOverlay.js";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { I } from "./icons.jsx";
import Tip from "./Tip.jsx";
import styles from "./Panels.module.css";

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
  const [pairing, setPairing] = useState("");
  const [pairBusy, setPairBusy] = useState(false);
  const [renaming, setRenaming] = useState(null);
  const [forgetFor, setForgetFor] = useState(null);
  const renameCancelled = useRef(false);
  async function submitPair() {
    if (!pairing.startsWith("alpi://") || pairBusy) return;
    setPairBusy(true);
    try {
      const ok = await onPair?.(pairing);
      if (ok !== false) setPairing("");
    } finally {
      setPairBusy(false);
    }
  }
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
              {locked ? "no host yet — add a connection to continue" : "where alpi runs"}
            </span>
          </div>
          {!locked && (
            <Tip text="Close" side="r">
              <button type="button" className="iconbtn" onClick={onClose}>
                <I.X />
              </button>
            </Tip>
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
                      <span className={`tag ${styles.tagUpdate}`}>update</span>
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
            <span className="eyebrow">Pair a new device</span>
            <span className={styles.pairFootHint}>
              Paste an{" "}
              <code className={`mono ${styles.pairCode}`}>alpi://</code> link
              from another machine
            </span>
          </div>
          <div className={`row row-gap ${styles.pairRow}`}>
            <input
              className={`field field-mono ${styles.pairInput}`}
              value={pairing}
              onChange={(e) => setPairing(e.target.value)}
              placeholder="alpi://device?url=wss%3A%2F%2Fclient.example.com&name=home&pairing_token=…"
            />
            <Button
              type="button"
              variant="primary"
          className={pairing.startsWith("alpi://") ? "" : styles.pairBtnDisabled}
              disabled={!pairing.startsWith("alpi://") || pairBusy}
              onClick={submitPair}
            >
              {pairBusy ? "Pairing…" : "Pair"}
            </Button>
          </div>
        </div>
      </PanelShell>
    </Scrim>
  );
}

export function Palette({ open, onClose, groups = [] }) {
  const [q, setQ] = useState("");
  const [idx, setIdx] = useState(0);
  const inputRef = useRef(null);

  useEffect(() => {
    if (open) {
      setQ("");
      setIdx(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  const flat = useMemo(() => {
    const out = [];
    groups.forEach((g) => {
      const filtered = q
        ? g.items.filter((it) =>
            it.label.toLowerCase().includes(q.toLowerCase()),
          )
        : g.items;
      if (filtered.length) {
        out.push({ kind: "header", label: g.label });
        filtered.forEach((it) => out.push({ kind: "item", ...it }));
      }
    });
    return out;
  }, [q, groups]);
  const items = flat.filter((x) => x.kind === "item");
  const actionableItems = items.filter((x) => x.onSelect);

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
  return (
    <Scrim onClose={onClose} top={120}>
      <PanelShell width={520} maxHeight="60vh">
        <div className={styles.paletteInputWrap}>
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setIdx(0);
            }}
            onKeyDown={onKey}
            placeholder="Type a command…"
            className={styles.paletteInput}
          />
        </div>
        <div className={`scroll ${styles.paletteBody}`}>
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
                <button
                  key={row.id}
                  type="button"
                  onClick={() => run(row)}
                  onMouseEnter={() => {
                    if (itemIndex >= 0) setIdx(itemIndex);
                  }}
                  aria-disabled={!actionable}
                  className={`row ${styles.paletteItem} ${selected ? styles.paletteItemSelected : ""} ${actionable ? "" : styles.paletteItemStatic}`}
                >
                  <span className={styles.paletteGlyph}>
                    {row.glyph || <I.ChevRight />}
                  </span>
                  <span className={styles.paletteLabel}>{row.label}</span>
                  {row.shortcut && (
                    <span className={styles.paletteShortcut}>
                      {row.shortcut.split("").map((ch, ci) => (
                        <span key={ci} className="kbd">
                          {ch}
                        </span>
                      ))}
                    </span>
                  )}
                </button>
              );
            })
          )}
        </div>
      </PanelShell>
    </Scrim>
  );
}
