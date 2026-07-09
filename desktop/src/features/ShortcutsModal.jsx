import Modal from "../primitives/Modal.jsx";
import { Kbd } from "../primitives/index.js";
import styles from "./ShortcutsModal.module.css";

const GROUPS = [
  {
    title: "General",
    items: [
      { keys: ["⌘", "K"], label: "Command palette" },
      { keys: ["⌘", "/"], label: "Keyboard shortcuts" },
      { keys: ["⌘", ","], label: "Settings" },
      { keys: ["⌘", "O"], label: "Notifications" },
      { keys: ["⇧", "⌘", "A"], label: "Bring Alpi to front" },
    ],
  },
  {
    title: "Navigate",
    items: [
      { keys: ["⌘", "1–9"], label: "Jump to alpi / workgroup" },
      { keys: ["⌘", "F"], label: "Find in transcript" },
      { keys: ["⇧", "⌘", "H"], label: "History: sessions / tasks" },
    ],
  },
  {
    title: "Create",
    items: [
      { keys: ["⌘", "N"], label: "New chat" },
      { keys: ["⇧", "⌘", "N"], label: "New profile" },
      { keys: ["⇧", "⌘", "W"], label: "New workgroup" },
      { keys: ["⌘", "↵"], label: "Send message" },
    ],
  },
  {
    title: "Browse",
    items: [
      { keys: ["⇧", "⌘", "T"], label: "Tools" },
      { keys: ["⇧", "⌘", "S"], label: "Skills" },
      { keys: ["⇧", "⌘", "M"], label: "Memory" },
    ],
  },
  {
    title: "View",
    items: [
      { keys: ["⌘", "+"], label: "Zoom in" },
      { keys: ["⌘", "-"], label: "Zoom out" },
      { keys: ["⌘", "0"], label: "Reset zoom" },
      { keys: ["Esc"], label: "Close / dismiss" },
    ],
  },
];

export default function ShortcutsModal({ open, onClose }) {
  if (!open) return null;
  return (
    <Modal open onClose={onClose} title="Keyboard shortcuts" closeButton width="var(--modal-md)">
      <div className={styles.grid}>
        {GROUPS.map((group) => (
          <div key={group.title} className={styles.group}>
            <div className={styles.groupTitle}>{group.title}</div>
            {group.items.map((item) => (
              <div key={item.label} className={styles.row}>
                <span className={styles.label}>{item.label}</span>
                <span className={styles.keys}>
                  {item.keys.map((k, i) => (
                    <Kbd key={i}>{k}</Kbd>
                  ))}
                </span>
              </div>
            ))}
          </div>
        ))}
      </div>
    </Modal>
  );
}
