import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../../primitives/Button.jsx";
import Chip from "../../../primitives/Chip.jsx";
import { useNotify } from "../../../primitives/Notification.jsx";
import { Row, ConfirmButton } from "../primitives.jsx";
import { STORAGE_SCOPE, formatBytes } from "../util.js";
import styles from "../../Settings.module.css";

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

export function SkillsField({ profile }) {
  const [items, setItems] = useState([]);
  useEffect(() => {
    invoke("skills", { profile: profile.name })
      .then(setItems)
      .catch(() => setItems([]));
  }, [profile.name]);

  if (items.length === 0) {
    return (
      <Row label="installed">
        <span className={styles.muted}>none</span>
      </Row>
    );
  }

  const grouped = new Map();
  for (const s of items) {
    const cat = s.category ?? "—";
    if (!grouped.has(cat)) grouped.set(cat, []);
    grouped.get(cat).push(s.name);
  }

  return (
    <>
      {[...grouped.entries()].map(([category, names]) => (
        <Row key={category} label={category} alignTop>
          <span className={styles.gatewayChips}>
            {names.map((n) => {
              const skill = items.find(
                (s) => s.name === n && (s.category ?? "—") === category,
              );
              return (
                <Chip
                  key={n}
                  size="sm"
                  tooltip={skill?.description || undefined}
                >
                  {n}
                </Chip>
              );
            })}
          </span>
        </Row>
      ))}
    </>
  );
}

export function DeleteProfileAction({ profile, onDeleted }) {
  const notify = useNotify();
  const [busy, setBusy] = useState(false);
  return (
    <span className={styles.inlineRow}>
      <ConfirmButton
        label="Delete profile"
        confirmLabel={`Confirm · wipe @${profile.name}`}
        loading={busy}
        onConfirm={async () => {
          setBusy(true);
          try {
            await invoke("profile_delete", { name: profile.name });
            notify({
              message: `Profile @${profile.name} deleted`,
              variant: "success",
            });
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
        }}
      />
      <span className={styles.muted}>
        removes ~/.alpi/profiles/{profile.name}/ — daemon picks up the
        change on its next restart
      </span>
    </span>
  );
}
