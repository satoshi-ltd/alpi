import { forwardRef, useLayoutEffect, useRef, useState } from "react";
import Button from "./Button.jsx";
import ConfirmDelete from "./ConfirmDelete.jsx";
import Fold from "./Fold.jsx";
import Icon from "./Icon.jsx";
import IconBtn from "./IconBtn.jsx";
import Popover from "./Popover.jsx";
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

function floating(el) {
  const style = getComputedStyle(el);
  const position = el.style?.position || style.position;
  return position === "absolute" || position === "fixed" || style.display === "none" || el.hidden || el.matches('[role="dialog"], [role="menu"], [role="tooltip"]');
}

export function trailingGhost(group) {
  const inFloat = (b) => {
    for (let n = b.parentElement; n && n !== group; n = n.parentElement) if (floating(n)) return true;
    return false;
  };
  const buttons = [...group.querySelectorAll("button")].filter((b) => !b.hidden && getComputedStyle(b).display !== "none" && !inFloat(b));
  const last = buttons.at(-1);
  if (!last || !/ghost$/.test(last.dataset.variant ?? "") || last.hasAttribute("data-filled") || !last.textContent.trim()) return null;
  for (let node = last; node && node !== group; node = node.parentElement) {
    for (let next = node.nextElementSibling; next; next = next.nextElementSibling) if (!floating(next)) return null;
  }
  return last;
}

function useTrailingEdge(ref) {
  useLayoutEffect(() => {
    const control = ref.current;
    if (!control) return undefined;
    const mark = () => {
      const groups = control.querySelectorAll(":scope > [data-field-line]");
      const marked = new Set([...(groups.length ? groups : [control])].map(trailingGhost).filter(Boolean));
      for (const b of control.querySelectorAll("[data-trailing]")) if (!marked.has(b)) b.removeAttribute("data-trailing");
      for (const b of marked) if (!b.hasAttribute("data-trailing")) b.setAttribute("data-trailing", "");
    };
    mark();
    if (typeof MutationObserver !== "function") return undefined;
    const observer = new MutationObserver(mark);
    observer.observe(control, { childList: true, subtree: true, attributes: true, attributeFilter: ["hidden", "style", "class", "data-variant"] });
    return () => observer.disconnect();
  }, [ref]);
}

export function Field({ label, children, helper, align = "center", stacked = false, hidden = false, searchable = false }) {
  const controlRef = useRef(null);
  useTrailingEdge(controlRef);
  const rowAlign = stacked ? styles.fieldRowStacked : align === "center" ? styles.fieldRowCenter : styles.fieldRowTop;
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
      <div ref={controlRef} className={`row ${styles.fieldControl}`}>{children}</div>
    </div>
  );
}

export function FieldLine({ children }) {
  return <div className={styles.fieldLine} data-field-line="">{children}</div>;
}

export function MemberRow({ member, isHub, note, owns = null, onRemove, onOpen, onCopyId, copyLabel = "Copy profile id" }) {
  const [confirm, setConfirm] = useState(false);
  const [menu, setMenu] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const run = (fn) => () => {
    setMenu(false);
    fn?.();
  };
  const hasMenu = onOpen || onCopyId || (!isHub && onRemove);
  return (
    <div className={`col ${styles.memberRow}`}>
      <div className={`row ${styles.memberHead}`}>
        <Fold shape={member.shape} color={member.color} />
        {member.accent ? (
          <span className={styles.memberName}>{member.id}</span>
        ) : (
          <span className={styles.memberName}>{member.id}</span>
        )}
        {isHub && <span className={styles.memberHubTag}>hub</span>}
        <span className={styles.memberSpacer} />
        {hasMenu && (
          <span className={styles.memberMenuWrap}>
            <IconBtn tip="More" tipSide="l" aria-label={`More for @${member.id}`} aria-expanded={menu} onClick={() => setMenu((o) => !o)}>
              <Icon name="ellipsis" />
            </IconBtn>
            <Popover open={menu} onClose={() => setMenu(false)} align="right" navigable role="menu">
              <div className={styles.memberMenu}>
                {onOpen && (
                  <Button role="menuitem" fullWidth className={styles.memberMenuItem} onClick={run(onOpen)}>
                    Open @{member.id}
                  </Button>
                )}
                {onCopyId && (
                  <Button role="menuitem" fullWidth className={styles.memberMenuItem} onClick={run(onCopyId)}>
                    {copyLabel}
                  </Button>
                )}
                {!isHub && onRemove && (
                  <Button role="menuitem" fullWidth className={`${styles.memberMenuItem} ${styles.memberMenuDanger}`} onClick={run(() => setConfirm(true))}>
                    Remove from workgroup…
                  </Button>
                )}
              </div>
            </Popover>
          </span>
        )}
      </div>
      {note && (
        <button
          type="button"
          className={`${styles.memberNote} ${expanded ? styles.memberNoteOpen : ""}`}
          aria-expanded={expanded}
          onClick={() => setExpanded((e) => !e)}
        >
          {note}
        </button>
      )}
      {Array.isArray(owns) && (
        <div className={`row ${styles.memberOwns}`}>
          <span className={styles.memberOwnsLabel}>owns</span>
          {owns.length > 0
            ? owns.map((slug) => <span key={slug} className={styles.memberOwnsTag}>#{slug}</span>)
            : <span className={styles.memberOwnsNone}>{isHub ? "none · the hub routes every phase" : "no phase"}</span>}
        </div>
      )}
      <ConfirmDelete
        open={confirm}
        onClose={() => setConfirm(false)}
        onConfirm={onRemove}
        title={`Remove @${member.id}?`}
        consequence="They lose access to this workgroup. Their copy of the thread stays intact."
        confirmLabel="Remove"
      />
    </div>
  );
}
