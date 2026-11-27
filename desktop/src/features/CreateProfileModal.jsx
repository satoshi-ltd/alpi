import { useEffect, useId, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { DialogFooter, Eyebrow, Field, Modal } from "../primitives/index.js";
import { useNotify } from "../primitives/Notification.jsx";
import { isValidProfileName, RESERVED_PROFILE_NAMES } from "../lib/profile-display.js";
import ProviderPickerForm, {
  applyProvider,
  daemonMessage,
  defaultProviderValue,
  isProviderValueValid,
  SIGN_IN_CANCELLED,
  signInCancelled,
  signedInNotice,
} from "./settings/ProviderPickerForm.jsx";
import styles from "./CreateProfileModal.module.css";
import { isComposing } from "../lib/composition.js";

export default function CreateProfileModal({
  open,
  existingNames = [],
  onCreated,
  onCreatedBehind,
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

  // A daemon that predates the ChatGPT sign-in rejects the verb, and the option stays out.
  const [chatgpt, setChatgpt] = useState(null);
  const probeProfile = existingNames[0];
  useEffect(() => {
    if (!open || !probeProfile) return undefined;
    let cancelled = false;
    setChatgpt(null);
    invoke("chatgpt_status", { profile: probeProfile })
      .then(() => {
        if (!cancelled) setChatgpt({ signed_in: false });
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [open, probeProfile]);

  const waitingRef = useRef(false);
  waitingRef.current = busy && providerValue.id === "chatgpt-plan";
  const openRef = useRef(open);
  const attemptRef = useRef(0);
  if (openRef.current !== open) {
    openRef.current = open;
    attemptRef.current += 1;
  }
  // Closing the dialog by any route ends the wait: its answer would otherwise open Settings minutes later.
  useEffect(() => {
    if (!open && waitingRef.current) invoke("chatgpt_sign_in_cancel").catch(() => {});
  }, [open]);

  const trimmed = name.trim();
  const reserved = RESERVED_PROFILE_NAMES.includes(trimmed);
  const errorId = useId();
  const formatValid = isValidProfileName(trimmed);
  const duplicate = existingNames.includes(trimmed);
  const providerOk = isProviderValueValid(providerValue);
  const canSubmit =
    !busy && formatValid && !duplicate && !reserved && providerOk;

  async function submit() {
    if (!canSubmit) return;
    const attempt = attemptRef.current;
    setBusy(true);
    try {
      await invoke("profile_create", { name: trimmed });
      try {
        if (providerValue.id === "chatgpt-plan" && attempt !== attemptRef.current) throw new Error(SIGN_IN_CANCELLED);
        const msg = await applyProvider(trimmed, providerValue);
        notify(providerValue.id === "chatgpt-plan" ? signedInNotice(msg) : { message: `Profile @${trimmed} created · ${msg}`, variant: "success" });
      } catch (e) {
        const plan = providerValue.id === "chatgpt-plan";
        notify(plan && signInCancelled(e)
          ? { message: `Profile @${trimmed} created. Sign in from its Providers.`, variant: "success" }
          : {
            message: plan
              ? `Profile @${trimmed} created. Sign-in failed: ${daemonMessage(e)}`
              : `Profile @${trimmed} created but provider step failed: ${String(e)}`,
            variant: "error",
            duration: 6000,
          });
      }
      // The dialog was reopened for another profile: its owner must not close it or leave for this one.
      if (attempt !== attemptRef.current && openRef.current) onCreatedBehind?.(trimmed);
      else onCreated?.(trimmed);
    } catch (e) {
      notify({
        message: `create failed: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      if (attempt === attemptRef.current) setBusy(false);
    }
  }

  const dirty = trimmed !== "" || JSON.stringify(providerValue) !== JSON.stringify(defaultProviderValue());

  const nameError =
    trimmed !== "" && !formatValid
      ? "a–z, 0–9, '.', '_', '-'; must start with a letter or digit"
      : reserved
        ? `'${trimmed}' is reserved`
        : duplicate
          ? `@${trimmed} already exists`
          : null;

  if (!open) return null;

  return (
    <Modal open title="New profile" onClose={onClose} closeOnBackdrop={!dirty && !busy} width="var(--modal-md)">
      <div className={styles.body}>
        <div className={styles.field}>
          <Eyebrow>Name</Eyebrow>
          <Field
            value={name}
            onChange={(e) => setName(e.target.value.toLowerCase())}
            onKeyDown={(e) => {
              if (!isComposing(e) && e.key === "Enter" && canSubmit) submit();
            }}
            placeholder="work · personal · home-server"
            aria-invalid={nameError ? true : undefined}
            aria-describedby={nameError ? errorId : undefined}
            spellCheck={false}
            autoFocus
          />
          {nameError && (
            <span id={errorId} className={styles.error}>{nameError}</span>
          )}
          <span className={styles.helper}>
            Configure workspace, accent, peers, etc. after.
          </span>
        </div>

        <div className={styles.field}>
          <Eyebrow>Provider</Eyebrow>
          <ProviderPickerForm
            value={providerValue}
            onChange={setProviderValue}
            chatgpt={chatgpt ?? undefined}
            signingIn={busy && providerValue.id === "chatgpt-plan"}
          />
        </div>

        <div className={styles.footer}>
          <DialogFooter
            onCancel={busy && providerValue.id === "chatgpt-plan" ? () => invoke("chatgpt_sign_in_cancel").catch(() => {}) : onClose}
            cancelWhileLoading={busy && providerValue.id === "chatgpt-plan"}
            primaryLabel={providerValue.id === "chatgpt-plan" ? "Continue with ChatGPT" : "Create"}
            primaryDisabled={!canSubmit}
            primaryLoading={busy}
            onPrimary={submit}
          />
        </div>
      </div>
    </Modal>
  );
}
