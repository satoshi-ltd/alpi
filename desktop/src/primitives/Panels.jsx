import { useEffect, useMemo, useRef, useState } from "react";
import { I } from "./icons.jsx";
import Tip from "./Tip.jsx";
import styles from "./Panels.module.css";

export function Scrim({ onClose, children, align = "flex-start", top = 96, dismissable = true }) {
  useEffect(() => {
    if (!dismissable) return;
    const onKey = (e) => {
      if (e.key === "Escape") onClose?.();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, dismissable]);
  return (
    <div
      className={`anim-fade ${styles.scrim}`}
      onClick={(e) => {
        if (dismissable && e.target === e.currentTarget) onClose();
      }}
      style={{
        alignItems: align,
        padding: `${top}px 60px 60px`,
      }}
    >
      {children}
    </div>
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
  onPair,
  locked = false,
}) {
  const [pairing, setPairing] = useState("");
  const [pairBusy, setPairBusy] = useState(false);
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
            const dotColor =
              r.status === "connected" || r.status === "online"
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
                    <span className={styles.connName}>{r.name}</span>
                    {active && <span className="tag">current</span>}
                    {r.status === "offline" && (
                      <span className={`tag ${styles.tagOffline}`}>
                        offline
                      </span>
                    )}
                    {r.status === "disabled" && <span className="tag">disabled</span>}
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
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onForget?.(r);
                    }}
                    className={styles.forgetBtn}
                  >
                    Forget
                  </button>
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
            <button
              type="button"
              className={`btn btn-primary ${pairing.startsWith("alpi://") ? "" : styles.pairBtnDisabled}`}
              disabled={!pairing.startsWith("alpi://") || pairBusy}
              onClick={submitPair}
            >
              {pairBusy ? "Pairing…" : "Pair"}
            </button>
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
    if (e.key === "ArrowDown" || e.key === "Tab") {
      e.preventDefault();
      setIdx((i) => Math.min(actionableItems.length - 1, i + 1));
    } else if (e.key === "ArrowUp" || (e.shiftKey && e.key === "Tab")) {
      e.preventDefault();
      setIdx((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      run(actionableItems[idx]);
    } else if (e.key === "Escape") {
      onClose?.();
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
