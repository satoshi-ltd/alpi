import { useCallback, useId, useRef, useState } from "react";
import { WORKGROUP_SHAPE } from "../../../common/shapes.mjs";
import { MUTED_NAME, nameVars } from "../lib/nameVars.js";
import { useDismissOnOutside } from "../hooks/useDismissOnOutside.js";
import { ChevDownIcon, Fold, Tip } from "./index.js";
import styles from "./ChatHeader.module.css";

export function HeaderDetail({ label, children }) {
  return (
    <div className={styles.detail}>
      <span className={styles.detailLabel}>{label}</span>
      <span className={styles.detailValue}>{children}</span>
    </div>
  );
}

export default function ChatHeader({
  kind = "profile",
  id,
  accent,
  shape,
  bio,
  meta,
  right,
  paused = false,
  mark = null,
  state = null,
  label = null,
  flag = null,
  className = "",
}) {
  const isWg = kind === "workgroup";
  const trimmedBio = (bio || "").trim();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const menuId = useId();
  const nameId = useId();
  const moreId = useId();
  const close = useCallback(() => setOpen(false), []);
  useDismissOnOutside({ open, onClose: close, wrapRef });
  const glyph = isWg
    ? <Fold shape={WORKGROUP_SHAPE} color={accent} size="md" {...mark} state={paused ? "paused" : mark?.state} />
    : <Fold shape={shape} color={accent} size="md" state={paused ? "paused" : state || "idle"} />;
  const titleGlyph = trimmedBio
    ? <Tip text={trimmedBio} side="l">{glyph}</Tip>
    : glyph;
  return (
    <header className={["ds-chat-header", styles.bar, className].filter(Boolean).join(" ")} style={{ "--c": accent }} data-drag>
      <div ref={wrapRef} className={styles.titleWrap}>
        <div className={`title-row ${styles.titleRow}`} data-menu={meta ? "" : undefined}>
          {titleGlyph}
          <h1 id={nameId} className="ds-name" style={paused ? MUTED_NAME : isWg ? null : nameVars(accent)}>{id}</h1>
          {label ? <span className={styles.label}>{label}</span> : null}
          {flag ? <span className={styles.flag} data-flag={flag.tone || "warning"} role="img" aria-label={flag.label} title={flag.label} /> : null}
          {meta ? (
            <button
              type="button"
              className={styles.title}
              aria-haspopup="dialog"
              aria-expanded={open}
              aria-controls={menuId}
              aria-labelledby={`${nameId} ${moreId}`}
              onClick={() => setOpen((v) => !v)}
            >
              <span id={moreId} className={styles.srOnly}>details</span>
              <ChevDownIcon className={styles.chevron} />
            </button>
          ) : null}
        </div>
        {meta && (
          <div id={menuId} role="dialog" aria-label={`${id} details`} className={`anim-menu ${styles.menu}`} hidden={!open} data-no-drag>
            {meta}
          </div>
        )}
      </div>
      <span className={styles.spring} />
      {right && <div className={`row ${styles.actions}`}>{right}</div>}
    </header>
  );
}
