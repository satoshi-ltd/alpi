import { useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../../primitives/Button.jsx";
import useAutoPosition from "../../../primitives/useAutoPosition.js";
import { useNotify } from "../../../primitives/Notification.jsx";
import { useDismissOnOutside } from "../../../hooks/useDismissOnOutside.js";
import { ConfirmDeleteAction, DialogFooter } from "../../../primitives/index.js";
import ProviderPickerForm, {
  applyProvider,
  defaultProviderValue,
  isProviderValueValid,
} from "../ProviderPickerForm.jsx";
import { PAID_PROVIDERS } from "../util.js";
import styles from "../Settings.module.css";

export function AddProviderField({ profile, onSaved }) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const anchorRef = useRef(null);
  const popoverRef = useRef(null);
  const pos = useAutoPosition({
    open,
    anchorRef,
    popoverRef,
    direction: "down",
    align: "right",
  });

  useDismissOnOutside({ open, onClose: () => setOpen(false), wrapRef });

  return (
    <span ref={wrapRef} className={styles.popoverAnchor}>
      <span ref={anchorRef}>
        <Button size="sm" onClick={() => setOpen((o) => !o)}>
          Providers
        </Button>
      </span>
      {open && (
        <div
          ref={popoverRef}
          className={styles.popover}
          style={{
            minWidth: 360,
            maxWidth: pos.maxWidth ?? undefined,
            width: "var(--pop-xl)",
            position: "fixed",
            top: pos.top,
            left: pos.left,
            right: "auto",
            bottom: "auto",
            visibility: pos.ready ? "visible" : "hidden",
          }}
        >
          <ProviderEditor
            profile={profile}
            onClose={() => setOpen(false)}
            onSaved={onSaved}
          />
        </div>
      )}
    </span>
  );
}

function ProviderEditor({ profile, onClose, onSaved }) {
  const notify = useNotify();
  const configured = profile.provider_keys ?? [];
  const configuredEnvs = new Set(configured.map((k) => k.env));
  const ollamas = profile.provider_ollama ?? [];
  const [providerValue, setProviderValue] = useState(defaultProviderValue());
  const [busy, setBusy] = useState(false);

  const savedOpenRouterModels = (profile.models ?? [])
    .filter((m) => m.startsWith("openrouter/"))
    .map((m) => m.slice("openrouter/".length));
  const canSave =
    !busy && isProviderValueValid(providerValue, { configuredEnvs });

  async function save() {
    if (!canSave) return;
    setBusy(true);
    try {
      const msg = await applyProvider(profile.name, providerValue);
      notify({ message: msg, variant: "success" });
      await onSaved?.();
      onClose?.();
    } catch (e) {
      notify({
        message: `add provider: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setBusy(false);
    }
  }

  async function removePaid(env, label) {
    try {
      await invoke("provider_unset_key", { profile: profile.name, key: env });
      notify({ message: `${label} key cleared`, variant: "success" });
      await onSaved?.();
    } catch (e) {
      notify({ message: `clear: ${String(e)}`, variant: "error", duration: 4000 });
    }
  }

  async function removeOllama(name) {
    try {
      await invoke("provider_remove_ollama", { profile: profile.name, name });
      notify({ message: `Ollama @${name} removed`, variant: "success" });
      await onSaved?.();
    } catch (e) {
      notify({ message: `remove: ${String(e)}`, variant: "error", duration: 4000 });
    }
  }

  const hasAnyConfigured = configured.length > 0 || ollamas.length > 0;

  return (
    <>
      {hasAnyConfigured && (
        <div className={styles.field}>
          <label className={styles.label}>configured</label>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
            {PAID_PROVIDERS.filter((p) => configuredEnvs.has(p.env)).map((p) => {
              const preview =
                configured.find((k) => k.env === p.env)?.preview ?? "";
              return (
                <span
                  key={p.env}
                  className={`${styles.inlineRow} ${styles.inlineRowSpaceBetween}`}
                >
                  <span>
                    <strong>{p.label}</strong>{" "}
                    <span className={`${styles.muted} ${styles.mono}`}>
                      · {preview}
                    </span>
                  </span>
                  <ConfirmDeleteAction
                    label="Remove"
                    title={`Remove ${p.label} provider?`}
                    consequence="The stored API key is wiped. You can add it again any time."
                    confirmLabel="Remove"
                    onConfirm={() => removePaid(p.env, p.label)}
                  />
                </span>
              );
            })}
            {ollamas.map((o) => (
              <span
                key={o.name}
                className={`${styles.inlineRow} ${styles.inlineRowSpaceBetween}`}
              >
                <span>
                  <strong>Ollama @{o.name}</strong>{" "}
                  <span className={styles.muted}>· {o.url}</span>
                </span>
                <ConfirmDeleteAction
                  label="Remove"
                  title={`Remove Ollama @${o.name}?`}
                  consequence="The Ollama endpoint is unregistered from this profile. Local models stay on disk."
                  confirmLabel="Remove"
                  onConfirm={() => removeOllama(o.name)}
                />
              </span>
            ))}
          </div>
        </div>
      )}

      <div className={styles.field}>
        <label className={styles.label}>add new</label>
        <ProviderPickerForm
          value={providerValue}
          onChange={setProviderValue}
          configuredEnvs={configuredEnvs}
          savedOpenRouterModels={savedOpenRouterModels}
          autoFocusFirstField
        />
      </div>

      <DialogFooter
        onCancel={onClose}
        primaryLabel="Save"
        primaryDisabled={!canSave}
        primaryLoading={busy}
        onPrimary={save}
      />
    </>
  );
}
