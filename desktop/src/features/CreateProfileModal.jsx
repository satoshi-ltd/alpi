import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { DialogFooter, Eyebrow, Modal } from "../primitives/index.js";
import { useNotify } from "../primitives/Notification.jsx";
import { RESERVED_PROFILE_NAMES } from "../lib/profile-display.js";
import ProviderPickerForm, {
  applyProvider,
  defaultProviderValue,
  isProviderValueValid,
} from "./settings/ProviderPickerForm.jsx";
import styles from "./CreateProfileModal.module.css";

export default function CreateProfileModal({
  open,
  existingNames = [],
  onCreated,
  onClose,
}) {
  const [name, setName] = useState("");
  const [providerValue, setProviderValue] = useState(defaultProviderValue());
  const [busy, setBusy] = useState(false);
  const notify = useNotify();

  useEffect(() => {
    if (!open) return;
    setName("");
    setProviderValue(defaultProviderValue());
    setBusy(false);
  }, [open]);

  const trimmed = name.trim();
  const reserved = RESERVED_PROFILE_NAMES.includes(trimmed);
  const formatValid = trimmed !== "" && /^[a-z0-9_-]+$/.test(trimmed);
  const duplicate = existingNames.includes(trimmed);
  const providerOk = isProviderValueValid(providerValue);
  const canSubmit =
    !busy && formatValid && !duplicate && !reserved && providerOk;

  async function submit() {
    if (!canSubmit) return;
    setBusy(true);
    try {
      await invoke("profile_create", { name: trimmed });
      try {
        const msg = await applyProvider(trimmed, providerValue);
        notify({ message: `Profile @${trimmed} created · ${msg}`, variant: "success" });
      } catch (e) {
        notify({
          message: `Profile @${trimmed} created but provider step failed: ${String(e)}`,
          variant: "error",
          duration: 6000,
        });
      }
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

  if (!open) return null;

  return (
    <Modal open title="New profile" onClose={onClose} width="var(--modal-md)">
      <div className={styles.body}>
        <div className={styles.field}>
          <Eyebrow>NAME</Eyebrow>
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
          {trimmed !== "" && !formatValid && (
            <span className={styles.error}>
              use a–z, 0–9, '-' and '_' only
            </span>
          )}
          {reserved && (
            <span className={styles.error}>'{trimmed}' is reserved</span>
          )}
          {duplicate && (
            <span className={styles.error}>@{trimmed} already exists</span>
          )}
          <span className={styles.helper}>
            Configure workspace, accent, peers, etc. after.
          </span>
        </div>

        <div className={styles.field}>
          <Eyebrow>PROVIDER · PICK ONE TO START</Eyebrow>
          <ProviderPickerForm
            value={providerValue}
            onChange={setProviderValue}
          />
        </div>

        <div className={styles.footer}>
          <DialogFooter
            onCancel={onClose}
            primaryLabel="Create"
            primaryDisabled={!canSubmit}
            primaryLoading={busy}
            onPrimary={submit}
          />
        </div>
      </div>
    </Modal>
  );
}
