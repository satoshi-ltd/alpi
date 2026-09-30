import { Scrim, PanelShell } from "../primitives/Panels.jsx";
import { Icon, IconBtn, KeyHint } from "../primitives/index.js";
import { SHORTCUTS } from "../lib/shortcuts.js";
import styles from "./ShortcutsSheet.module.css";

export function groupShortcuts(list = SHORTCUTS) {
  const out = new Map();
  for (const s of list) {
    if (!out.has(s.group)) out.set(s.group, []);
    out.get(s.group).push(s);
  }
  return Array.from(out.entries());
}

export default function ShortcutsSheet({ open, onClose }) {
  if (!open) return null;
  return (
    <Scrim onClose={onClose} top={80}>
      <PanelShell width={620} maxHeight="76vh">
        <div className={styles.head}>
          <span className={styles.title}>Keyboard shortcuts</span>
          <KeyHint hint="⌘/" />
          <IconBtn tip="Close" tipSide="l" onClick={onClose}>
            <Icon name="x" />
          </IconBtn>
        </div>
        <div className={`scroll ${styles.body}`}>
          {groupShortcuts().map(([group, items]) => (
            <section key={group} className={styles.group} aria-label={group}>
              <h3 className={`eyebrow ${styles.groupLabel}`}>{group}</h3>
              <dl className={styles.list}>
                {items.map((s) => (
                  <div key={s.id} className={styles.row}>
                    <dt className={styles.label}>{s.label}</dt>
                    <dd className={styles.keys}><KeyHint hint={s.keys} /></dd>
                  </div>
                ))}
              </dl>
            </section>
          ))}
        </div>
      </PanelShell>
    </Scrim>
  );
}
