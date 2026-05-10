import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../primitives/Button.jsx";
import { useNotify } from "../../primitives/Notification.jsx";
import { RESERVED_PROFILE_NAMES } from "../../lib/profile-display.js";
import { Section, Row } from "./primitives.jsx";
import styles from "../Settings.module.css";

export default function CreateProfileForm({ existingNames, onCreated, onCancel }) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const notify = useNotify();

  const trimmed = name.trim();
  const reserved = RESERVED_PROFILE_NAMES.includes(trimmed);
  const formatValid = trimmed !== "" && /^[a-z0-9_-]+$/.test(trimmed);
  const duplicate = existingNames.includes(trimmed);
  const canSubmit = !busy && formatValid && !duplicate && !reserved;

  async function submit() {
    if (!canSubmit) return;
    setBusy(true);
    try {
      await invoke("profile_create", { name: trimmed });
      notify({ message: `Profile @${trimmed} created`, variant: "success" });
      onCreated?.(trimmed);
    } catch (e) {
      notify({
        message: `create failed: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className={styles.detail}>
      <div className={styles.body}>
        <Section title="New profile">
          <Row label="name">
            <span className={styles.inlineRow}>
              <input
                className={styles.input}
                value={name}
                onChange={(e) => setName(e.target.value.toLowerCase())}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && canSubmit) submit();
                }}
                placeholder="work · personal · home-server"
                spellCheck={false}
                autoFocus
              />
            </span>
          </Row>
          {trimmed !== "" && !formatValid && (
            <Row label=" ">
              <span className={styles.error}>
                use a-z, 0-9, '-' and '_' only
              </span>
            </Row>
          )}
          {reserved && (
            <Row label=" ">
              <span className={styles.error}>'{trimmed}' is reserved</span>
            </Row>
          )}
          {duplicate && (
            <Row label=" ">
              <span className={styles.error}>@{trimmed} already exists</span>
            </Row>
          )}
          <Row label=" ">
            <span className={styles.muted}>
              configure model, workspace, peers, etc. after.
            </span>
          </Row>
          <Row label=" ">
            <span className={styles.inlineRow}>
              <Button onClick={onCancel} disabled={busy}>Cancel</Button>
              <Button
                variant="primary"
                onClick={submit}
                disabled={!canSubmit}
                loading={busy}
              >
                Create
              </Button>
            </span>
          </Row>
        </Section>
      </div>
    </main>
  );
}
