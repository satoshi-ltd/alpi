import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../../primitives/Button.jsx";
import Chip from "../../../primitives/Chip.jsx";
import { useNotify } from "../../../primitives/Notification.jsx";
import { Row } from "../primitives.jsx";
import { ConfirmDelete } from "../../../primitives/index.js";
import { Btn } from "../../../primitives/index.js";
import { STORAGE_SCOPE, formatBytes } from "../util.js";
import styles from "../Settings.module.css";

export function StorageField({ profile }) {
  const [items, setItems] = useState([]);
  useEffect(() => {
    invoke("profile_storage", { profile: profile.name })
      .then(setItems)
      .catch(() => setItems([]));
  }, [profile.name]);

  const visible = items.filter(
    (it) => it.size_bytes > 0 || it.file_count > 0,
  );

  if (visible.length === 0) {
    return (
      <Row label="size">
        <span className={styles.muted}>nothing yet</span>
      </Row>
    );
  }

  return (
    <>
      {visible.map((it) => (
        <Row key={it.key} label={it.label}>
          <span className={styles.inlineRow}>
            <Chip size="sm" tooltip={STORAGE_SCOPE[it.key]}>
              {formatBytes(it.size_bytes)}
            </Chip>
            <Chip size="sm">
              {it.file_count} {it.file_count === 1 ? "file" : "files"}
            </Chip>
            <Button
              size="sm"
              onClick={() => invoke("reveal_in_finder", { path: it.path })}
            >
              Reveal
            </Button>
          </span>
        </Row>
      ))}
    </>
  );
}

export function DeleteProfileAction({ profile, onDeleted }) {
  const notify = useNotify();
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);

  async function doDelete() {
    setBusy(true);
    try {
      await invoke("profile_delete", { name: profile.name });
      notify({ message: `Profile @${profile.name} deleted`, variant: "success" });
      await onDeleted?.();
    } catch (e) {
      notify({
        message: `delete failed: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className={styles.inlineRow}>
      <Btn
        variant="ghost"
        disabled={busy}
        style={{ color: "var(--c-danger)" }}
        onClick={() => setOpen(true)}
      >
        Delete profile
      </Btn>
      <span className={styles.muted}>
        removes ~/.alpi/profiles/{profile.name}/ — daemon picks up the
        change on its next restart
      </span>
      <ConfirmDelete
        mode="typed"
        open={open}
        onClose={() => setOpen(false)}
        onConfirm={doDelete}
        title={`Delete profile @${profile.name}?`}
        consequence={`This wipes ~/.alpi/profiles/${profile.name}/ on disk — sessions, RAG, ALP keypair, every secret stored under it. Cannot be undone.`}
        typeToConfirm={profile.name}
        confirmLabel={`Delete @${profile.name}`}
      />
    </span>
  );
}
