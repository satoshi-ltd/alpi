import { forwardRef, useEffect, useRef, useState } from "react";
import { I } from "./icons.jsx";
import ConfirmDelete from "./ConfirmDelete.jsx";
import Diamond from "./Diamond.jsx";
import IconBtn from "./IconBtn.jsx";
import Selectish from "./Selectish.jsx";
import { useDismissOnOutside } from "../hooks/useDismissOnOutside.js";
import { ACCENTS } from "../../../common/accents.mjs";
import styles from "./SettingsLayout.module.css";

export const Section = forwardRef(function Section({ label, children, kicker, id, hidden = false }, ref) {
  return (
    <section
      ref={ref}
      id={id}
      hidden={hidden}
      data-settings-section={typeof label === "string" ? label : undefined}
      className={styles.section}
    >
      <div className={`row ${styles.sectionHead}`}>
        <h3 className={styles.sectionTitle}>{label}</h3>
        {kicker && <span className={styles.sectionKicker}>{kicker}</span>}
      </div>
      <div className={`col ${styles.sectionBody}`}>{children}</div>
    </section>
  );
});

export function Field({ label, children, helper, align = "center", hidden = false, searchable = false }) {
  const rowAlign = align === "center" ? styles.fieldRowCenter : styles.fieldRowTop;
  // `hidden` keeps the same element so children stay mounted while the row is out of view.
  return (
    <div
      className={`row ${styles.fieldRow} ${rowAlign}`}
      hidden={hidden}
      data-settings-row={searchable ? "" : undefined}
    >
      <div
        className={`${styles.fieldLabelCol} ${align === "top" ? styles.fieldLabelColTop : ""}`}
      >
        <div className={styles.fieldLabel}>{label}</div>
        {helper && <div className={styles.fieldHelper}>{helper}</div>}
      </div>
      <div className={`row ${styles.fieldControl}`}>{children}</div>
    </div>
  );
}

export function AccentPicker({ value, onChange }) {
  const [open, setOpen] = useState(false);
  const [hex, setHex] = useState(value || "#f0b447");
  const ref = useRef(null);

  useDismissOnOutside({ open, onClose: () => setOpen(false), wrapRef: ref });

  useEffect(() => {
    setHex(value || "#f0b447");
  }, [value]);

  const isValidHex = /^#[0-9a-f]{6}$/i.test(hex);
  const commit = (c) => {
    setHex(c);
    onChange?.(c);
  };

  return (
    <span ref={ref} className={styles.accentPickerWrap}>
      <Selectish
        leading={<Diamond color={value} />}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        {value}
      </Selectish>
      {open && (
        <div className={`anim-pop ${styles.accentPopover}`}>
          <div className={styles.swatchGrid}>
            {ACCENTS.map(([name, c]) => {
              const sel = value?.toLowerCase() === c.toLowerCase();
              return (
                <IconBtn
                  key={c}
                  tip={`${name} · ${c}`}
                  tipSide="up"
                  aria-label={`${name} ${c}`}
                  aria-pressed={sel}
                  onClick={() => commit(c)}
                  className={`${styles.swatchChip} ${sel ? styles.swatchChipSelected : ""}`}
                >
                  <Diamond color={c} size="md" className={styles.swatchDiamond} />
                </IconBtn>
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
          <IconBtn tip="Remove from workgroup" tipSide="l" onClick={() => setConfirm(true)}>
            <I.X />
          </IconBtn>
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
