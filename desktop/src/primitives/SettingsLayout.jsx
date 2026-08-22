import { useEffect, useRef, useState } from "react";
import { I } from "./icons.jsx";
import Tip from "./Tip.jsx";
import ConfirmDelete from "./ConfirmDelete.jsx";
import Diamond from "./Diamond.jsx";
import { useDismissOnOutside } from "../hooks/useDismissOnOutside.js";
import { ACCENT_HEXES } from "../../../common/accents.mjs";
import styles from "./SettingsLayout.module.css";

function Anchored({ open, onClose, children, width = 320, align = "left" }) {
  const ref = useRef(null);
  useDismissOnOutside({ open, onClose, wrapRef: ref });
  if (!open) return null;
  return (
    <div
      ref={ref}
      className={`anim-pop ${styles.anchored} ${align === "right" ? styles.anchoredRight : styles.anchoredLeft}`}
      style={{ width }}
    >
      {children}
    </div>
  );
}

export function Section({ label, children, kicker }) {
  return (
    <section className={styles.section}>
      <div className={`row ${styles.sectionHead}`}>
        <h3 className={styles.sectionTitle}>{label}</h3>
        {kicker && <span className={styles.sectionKicker}>{kicker}</span>}
      </div>
      <div className={`col ${styles.sectionBody}`}>{children}</div>
    </section>
  );
}

export function Field({ label, children, helper, align = "center" }) {
  const rowAlign = align === "center" ? styles.fieldRowCenter : styles.fieldRowTop;
  return (
    <div className={`row ${styles.fieldRow} ${rowAlign}`}>
      <div
        className={`${styles.fieldLabelCol} ${align === "top" ? styles.fieldLabelColTop : ""}`}
      >
        <div className={`eyebrow ${styles.fieldLabel}`}>{label}</div>
        {helper && <div className={styles.fieldHelper}>{helper}</div>}
      </div>
      <div className={`row ${styles.fieldControl}`}>{children}</div>
    </div>
  );
}

export function ActionLink({ children, onClick, danger }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`${styles.actionLink} ${danger ? styles.actionLinkDanger : ""}`}
    >
      {children}
    </button>
  );
}

export function Selectish({ children, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`row row-gap ${styles.selectish}`}
    >
      {children}
      <I.ChevDown className={styles.chev} />
    </button>
  );
}

export function Popped({
  trigger,
  width = 320,
  children,
  mode = "selectish",
  align = "left",
}) {
  const [open, setOpen] = useState(false);
  const TriggerEl = mode === "selectish" ? Selectish : ActionLink;
  return (
    <span className={styles.poppedWrap}>
      <TriggerEl onClick={() => setOpen((o) => !o)}>{trigger}</TriggerEl>
      <Anchored
        open={open}
        onClose={() => setOpen(false)}
        width={width}
        align={align}
      >
        {typeof children === "function"
          ? children({ close: () => setOpen(false) })
          : children}
      </Anchored>
    </span>
  );
}

export function AccentPicker({ value, onChange }) {
  const [open, setOpen] = useState(false);
  const [hex, setHex] = useState(value || "#b8954a");
  const ref = useRef(null);

  useDismissOnOutside({ open, onClose: () => setOpen(false), wrapRef: ref });

  useEffect(() => {
    setHex(value || "#b8954a");
  }, [value]);

  const isValidHex = /^#[0-9a-f]{6}$/i.test(hex);
  const commit = (c) => {
    setHex(c);
    onChange?.(c);
  };

  return (
    <span ref={ref} className={styles.accentPickerWrap}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={`row row-gap ${styles.selectish}`}
      >
        <Diamond color={value} />
        <span>{value}</span>
        <I.ChevDown className={styles.chev} />
      </button>
      {open && (
        <div className={`anim-pop ${styles.accentPopover}`}>
          <div className={styles.swatchGrid}>
            {ACCENT_HEXES.map((c) => {
              const sel = value?.toLowerCase() === c.toLowerCase();
              return (
                <button
                  key={c}
                  type="button"
                  onClick={() => commit(c)}
                  title={c}
                  className={`${styles.swatchChip} ${sel ? styles.swatchChipSelected : ""}`}
                >
                  <Diamond color={c} size="md" className={styles.swatchDiamond} />
                </button>
              );
            })}
          </div>
          <input
            value={hex}
            onChange={(e) => {
              setHex(e.target.value);
              if (/^#[0-9a-f]{6}$/i.test(e.target.value))
                onChange?.(e.target.value);
            }}
            className={`field field-mono ${styles.hexInput}`}
            placeholder="#hex"
            spellCheck={false}
          />
          {!isValidHex && hex.length > 0 && (
            <div className={styles.hexError}>must be 6-digit #hex</div>
          )}
        </div>
      )}
    </span>
  );
}

export function MemberRow({ member, isHub, note, onRemove }) {
  const [confirm, setConfirm] = useState(false);
  return (
    <div className={`row ${styles.memberRow}`}>
      <div className={`col ${styles.memberIdent}`}>
        <div className={`row row-gap ${styles.memberIdentTop}`}>
          <span className="diamond" style={{ "--c": member.color }} />
          <span className={`mono ${styles.memberHandle}`}>@{member.id}</span>
        </div>
        {isHub && <span className={`mono ${styles.memberHubTag}`}>hub</span>}
      </div>
      <p className={styles.memberNote}>{note}</p>
      {!isHub && (
        <span className={styles.memberRemoveWrap}>
          <Tip text="Remove from workgroup" side="l">
            <button
              type="button"
              className="iconbtn"
              onClick={() => setConfirm(true)}
            >
              <I.X />
            </button>
          </Tip>
          <ConfirmDelete
            open={confirm}
            onClose={() => setConfirm(false)}
            onConfirm={onRemove}
            title={`Remove @${member.id}?`}
            consequence="They lose access to this workgroup. Their copy of the thread stays intact."
            confirmLabel="Remove"
          />
        </span>
      )}
    </div>
  );
}
