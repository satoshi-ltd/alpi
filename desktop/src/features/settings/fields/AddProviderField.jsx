import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../../primitives/Button.jsx";
import Eyebrow from "../../../primitives/Eyebrow.jsx";
import useAutoPosition from "../../../primitives/useAutoPosition.js";
import { useNotify } from "../../../primitives/Notification.jsx";
import { useDismissOnOutside } from "../../../hooks/useDismissOnOutside.js";
import { ConfirmDeleteAction, ConfirmSheet, DialogFooter } from "../../../primitives/index.js";
import ProviderPickerForm, {
  applyProvider,
  CHATGPT_PLAN,
  daemonMessage,
  defaultProviderValue,
  isProviderValueValid,
  signInCancelled,
  signedInNotice,
} from "../ProviderPickerForm.jsx";
import { runsOnPlan } from "../../../lib/modelLabel.js";
import { PAID_PROVIDERS } from "../util.js";
import useExit from "../../../hooks/useExit.js";
import styles from "../Settings.module.css";

export function AddProviderField({ profile, onSaved }) {
  const [open, setOpen] = useState(false);
  const { mounted, closing } = useExit(open);
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
      {mounted && (
        <div
          ref={popoverRef}
          inert={closing || undefined}
          className={`${closing ? "anim-menu-out " : pos.ready ? "anim-menu " : ""}${styles.popover}`}
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
          <ConfirmSheet inset="var(--sp-12)">
            <ProviderEditor
              profile={profile}
              onClose={() => setOpen(false)}
              onSaved={onSaved}
            />
          </ConfirmSheet>
        </div>
      )}
    </span>
  );
}

function ProviderEditor({ profile, onClose, onSaved }) {
  const notify = useNotify();
  const configured = profile.provider_keys ?? [];
  const configuredEnvs = new Set(configured.map((k) => k.env));
  const configuredPreviews = new Map(configured.map((k) => [k.env, k.preview]));
  const ollamas = profile.provider_ollama ?? [];
  const [providerValue, setProviderValue] = useState(defaultProviderValue());
  const [busy, setBusy] = useState(false);
  const [ollamaCounts, setOllamaCounts] = useState({});
  const [ollamaErrors, setOllamaErrors] = useState({});
  useEffect(() => {
    let cancelled = false;
    invoke("ollama_models", { profile: profile.name })
      .then((envelope) => {
        if (cancelled) return;
        const list = Array.isArray(envelope)
          ? envelope
          : Array.isArray(envelope?.models)
            ? envelope.models
            : [];
        const counts = {};
        for (const m of list) {
          const slash = m.indexOf("/");
          if (slash < 0) continue;
          const name = m.slice(0, slash);
          counts[name] = (counts[name] ?? 0) + 1;
        }
        setOllamaCounts(counts);
        const errs = {};
        const errsArr = Array.isArray(envelope?.errors) ? envelope.errors : [];
        for (const e of errsArr) errs[e.name] = e;
        setOllamaErrors(errs);
      })
      .catch(() => {
        if (!cancelled) {
          setOllamaCounts({});
          setOllamaErrors({});
        }
      });
    return () => {
      cancelled = true;
    };
  }, [profile.name, ollamas.length]);

  const savedOpenRouterModels = (profile.models ?? [])
    .filter((m) => m.startsWith("openrouter/"))
    .map((m) => m.slice("openrouter/".length));
  const canSave =
    !busy && isProviderValueValid(providerValue, { configuredEnvs });

  async function save() {
    if (!canSave) return;
    setBusy(true);
    try {
      const msg = await applyProvider(profile.name, providerValue, {
        currentModel: profile.model,
      });
      notify(providerValue.id === CHATGPT_PLAN.id ? signedInNotice(msg) : { message: msg, variant: "success" });
      await onSaved?.();
      onClose?.();
    } catch (e) {
      if (signInCancelled(e)) return;
      notify({
        message: providerValue.id === CHATGPT_PLAN.id ? daemonMessage(e) : `add provider: ${String(e)}`,
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

  async function signOutChatGPT() {
    try {
      const out = await invoke("chatgpt_sign_out", { profile: profile.name });
      const left = out?.model_cleared ? ` · @${profile.name} has no model` : "";
      notify(out?.revoked === false
        ? { message: `Signed out here only. Remove alpi in ChatGPT settings.${left}`, variant: "error", duration: 8000 }
        : { message: `Signed out${left}`, variant: "success" });
      await onSaved?.();
    } catch (e) {
      notify({ message: `Sign out failed: ${daemonMessage(e)}`, variant: "error", duration: 4000 });
    }
  }

  const waitingRef = useRef(false);
  waitingRef.current = busy && providerValue.id === CHATGPT_PLAN.id;
  // Leaving the form ends the wait: the browser's answer would otherwise land on nothing, five minutes later.
  useEffect(() => () => {
    if (waitingRef.current) invoke("chatgpt_sign_in_cancel").catch(() => {});
  }, []);

  function cancel() {
    if (waitingRef.current) invoke("chatgpt_sign_in_cancel").catch(() => {});
    onClose?.();
  }

  async function removeOllama(name) {
    try {
      await invoke("provider_remove_ollama", { profile: profile.name, name });
      notify({ message: `ollama/${name} removed`, variant: "success" });
      await onSaved?.();
    } catch (e) {
      notify({ message: `remove: ${String(e)}`, variant: "error", duration: 4000 });
    }
  }

  const selectedPaid = PAID_PROVIDERS.find((p) => p.id === providerValue.id);
  const selectedConfigured =
    selectedPaid && configuredEnvs.has(selectedPaid.env) ? selectedPaid : null;
  const showOllamaEndpoints = providerValue.id === "ollama" && ollamas.length > 0;
  const chatgpt = profile.provider_chatgpt;
  const chatgptSelected = providerValue.id === CHATGPT_PLAN.id;

  return (
    <>
      <div className={styles.field}>
        <Eyebrow as="label">Providers</Eyebrow>
        <ProviderPickerForm
          value={providerValue}
          onChange={setProviderValue}
          configuredEnvs={configuredEnvs}
          configuredPreviews={configuredPreviews}
          savedOpenRouterModels={savedOpenRouterModels}
          ollamaModelCount={Object.values(ollamaCounts).reduce((a, b) => a + b, 0)}
          ollamaEndpointCount={ollamas.length}
          providerCatalog={profile.provider_catalog}
          chatgpt={chatgpt}
          signingIn={busy && chatgptSelected}
          autoFocusFirstField
        />
        {showOllamaEndpoints && (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-8)" }}>
            {ollamas.map((o) => {
              const count = ollamaCounts[o.name];
              const err = ollamaErrors[o.name];
              return (
                <span
                  key={o.name}
                  className={`${styles.inlineRow} ${styles.inlineRowSpaceBetween} ${styles.inlineRowWrap}`}
                >
                  <span>
                    <strong>ollama/{o.name}</strong>{" "}
                    <span className={styles.muted}>· {o.url}</span>
                    {count != null && count > 0 ? (
                      <span className={styles.muted}>
                        {" "}
                        · {count} model{count === 1 ? "" : "s"}
                      </span>
                    ) : null}
                    {err ? (
                      <span className={styles.warnBlockTight}>
                        unreachable — {err.detail}
                      </span>
                    ) : null}
                  </span>
                  <ConfirmDeleteAction
                    label="Remove"
                    title={`Remove ollama/${o.name}?`}
                    consequence="The Ollama endpoint is unregistered from this profile. Local models stay on disk."
                    confirmLabel="Remove"
                    onConfirm={() => removeOllama(o.name)}
                  />
                </span>
              );
            })}
          </div>
        )}
      </div>

      <DialogFooter
        leading={
          selectedConfigured ? (
            <ConfirmDeleteAction
              label={`Remove ${selectedConfigured.label}`}
              title={`Remove ${selectedConfigured.label} provider?`}
              consequence="The stored API key is wiped. You can add it again any time."
              confirmLabel="Remove"
              onConfirm={() => removePaid(selectedConfigured.env, selectedConfigured.label)}
            />
          ) : chatgptSelected && (chatgpt?.signed_in || chatgpt?.plan_declined || chatgpt?.registered) ? (
            <ConfirmDeleteAction
              label="Sign out"
              title="Sign out?"
              consequence={runsOnPlan(profile.model)
                ? `@${profile.name} is left without a model.`
                : `@${profile.name} can no longer use plan models.`}
              confirmLabel="Sign out"
              onConfirm={signOutChatGPT}
            />
          ) : null
        }
        onCancel={cancel}
        cancelWhileLoading={busy && chatgptSelected}
        primaryLabel={chatgptSelected ? (chatgpt?.signed_in ? undefined : "Continue with ChatGPT") : "Save"}
        primaryDisabled={!canSave}
        primaryLoading={busy}
        onPrimary={save}
      />
    </>
  );
}
