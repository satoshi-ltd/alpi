import { forwardRef, useState } from "react";
import { I } from "./icons.jsx";
import ConfirmDelete from "./ConfirmDelete.jsx";
import Fold from "./Fold.jsx";
import IconBtn from "./IconBtn.jsx";
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

export function MemberRow({ member, isHub, note, onRemove }) {
  const [confirm, setConfirm] = useState(false);
  return (
    <div className={`row ${styles.memberRow}`}>
      <div className={`col ${styles.memberIdent}`}>
        <div className={`row row-gap ${styles.memberIdentTop}`}>
          <Fold fold={member.fold} color={member.color} />
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
