import { useState } from "react";
import { Button, DownloadIcon, Icon, IconBtn, Popover, Tip } from "../primitives/index.js";
import { useNotify } from "../primitives/Notification.jsx";
import { downloadMarkdown, printMessage } from "../lib/messageExport.js";
import styles from "./ExportMenu.module.css";

export function useMessageExport() {
  const notify = useNotify();
  const download = async (message) => {
    try {
      const meta = await downloadMarkdown(message);
      notify({ message: `Downloaded ${meta.name}` });
    } catch (e) {
      notify({ message: `Download failed: ${e}`, variant: "error" });
    }
  };
  const print = async (message, accent) => {
    try {
      await printMessage(message, accent);
    } catch (e) {
      notify({ message: `Export failed: ${e}`, variant: "error" });
    }
  };
  return { download, print };
}

export default function ExportMenu({ message, accent, className = "" }) {
  const [open, setOpen] = useState(false);
  const { download, print } = useMessageExport();
  const run = (fn) => () => {
    setOpen(false);
    fn();
  };
  return (
    <span className={styles.anchor}>
      <Tip text="Download" side="up">
        <IconBtn aria-label="Download" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)} className={className}>
          <DownloadIcon size="sm" />
        </IconBtn>
      </Tip>
      <Popover open={open} onClose={() => setOpen(false)} side="top" navigable role="menu">
        <div className={styles.menu}>
          <Button role="menuitem" fullWidth className={styles.item} onClick={run(() => download(message))}>
            <DownloadIcon className={styles.icon} />
            <span className={styles.label}>Download .md</span>
          </Button>
          <Button role="menuitem" fullWidth className={styles.item} onClick={run(() => print(message, accent))}>
            <Icon name="file-text" className={styles.icon} />
            <span className={styles.label}>Export PDF…</span>
          </Button>
        </div>
      </Popover>
    </span>
  );
}
