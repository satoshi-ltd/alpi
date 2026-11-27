import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { ActionLink, Eyebrow, Field } from "../../primitives/index.js";
import Dropdown from "../../primitives/Dropdown.jsx";
import { PAID_PROVIDERS } from "./util.js";
import { openExternal } from "../../lib/openExternal.js";
import { CHATGPT_USAGE_URL } from "../../lib/modelLabel.js";
import styles from "./ProviderPickerForm.module.css";

// Ordered by how often a profile actually needs them, not alphabetically.
const PROVIDER_ORDER = ["ollama", "openrouter", "anthropic", "openai", "chatgpt-plan", "gemini", "groq"];
export const CHATGPT_PLAN = { id: "chatgpt-plan", label: "ChatGPT plan" };
export const SIGN_IN_CANCELLED = "sign-in cancelled";
const PLAN_DECLINED = "Plan use was declined. Sign in again to allow it.";
export const PLAN_WELCOME = "You're using your ChatGPT plan";

// OpenAI asks for a confirmation the person dismisses, the first time a sign-in turns plan use on.
export function signedInNotice(message) {
  if (!String(message).startsWith(PLAN_WELCOME)) return { message, variant: "success" };
  return {
    message, variant: "success", persistent: true, action: "Manage usage",
    onAction: () => openExternal(CHATGPT_USAGE_URL).catch(() => {}),
  };
}

// A daemon error reaches the app as "alp <code>: <name> — <what happened>"; people only need the last part.
export function daemonMessage(error) {
  const text = String(error?.message ?? error ?? "").replace(/^Error:\s*/, "");
  const at = text.lastIndexOf(" — ");
  return at >= 0 ? text.slice(at + 3) : text;
}

export function signInCancelled(error) {
  return String(error?.message ?? error ?? "").includes(SIGN_IN_CANCELLED);
}

function plural(n, word) {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

const PROVIDER_OPTIONS = PROVIDER_ORDER.map(
  (id) =>
    id === "ollama"
      ? { id: "ollama", label: "Ollama" }
      : id === CHATGPT_PLAN.id
        ? CHATGPT_PLAN
        : PAID_PROVIDERS.find((p) => p.id === id),
).filter(Boolean);

export function providerHint(
  id,
  {
    configuredEnvs,
    configuredPreviews,
    providerCatalog,
    ollamaModelCount = 0,
    ollamaEndpointCount = 0,
    chatgpt,
  } = {},
) {
  if (id === "ollama") {
    if (!ollamaEndpointCount) return "local · no API key";
    return `local · ${plural(ollamaModelCount, "model")}`;
  }
  if (id === CHATGPT_PLAN.id) {
    if (chatgpt?.signed_in) return [plural(chatgpt.models ?? 0, "model"), chatgpt.email || "signed in"].join(" · ");
    if (chatgpt?.plan_declined) return "plan use declined";
    return "needs sign-in";
  }
  const meta = PAID_PROVIDERS.find((p) => p.id === id);
  if (!meta) return "";
  const count = providerCatalog?.[meta.env];
  const models = count == null ? "" : plural(count, "model");
  if (configuredEnvs?.has?.(meta.env)) {
    const preview = configuredPreviews?.get?.(meta.env);
    return [models, preview ? `key · ${preview}` : "key set"].filter(Boolean).join(" · ");
  }
  return [models, "needs a key"].filter(Boolean).join(" · ");
}

export function defaultProviderValue() {
  return { id: "ollama", name: "", url: "http://localhost:11434" };
}

export function isProviderValueValid(value, { configuredEnvs } = {}) {
  if (!value) return false;
  if (value.id === CHATGPT_PLAN.id) return true;
  if (value.id === "ollama") {
    const name = (value.name || "").trim();
    const url = (value.url || "").trim();
    return name.length > 0 && /^[a-z0-9_-]+$/.test(name) && url.length > 0;
  }
  const meta = PAID_PROVIDERS.find((p) => p.id === value.id);
  if (!meta) return false;
  const keyAlreadySet = configuredEnvs?.has?.(meta.env) ?? false;
  const trimmedKey = (value.keyValue || "").trim();
  const keyOk = keyAlreadySet || trimmedKey.length > 0;
  return keyOk;
}

export async function applyProvider(profile, value, { currentModel } = {}) {
  if (value.id === "ollama") {
    const name = value.name.trim();
    const url = value.url.trim().replace(/\/$/, "");
    await invoke("provider_add_ollama", { profile, name, url });
    return `Ollama @${name} added`;
  }
  if (value.id === CHATGPT_PLAN.id) {
    const out = await invoke("chatgpt_sign_in", { profile });
    if (!out?.signed_in) throw new Error(PLAN_DECLINED);
    const who = out.email || "your account";
    return out.first_sign_in ? `${PLAN_WELCOME} · ${who}` : `Signed in as ${who}`;
  }
  const meta = PAID_PROVIDERS.find((p) => p.id === value.id);
  const trimmedKey = (value.keyValue || "").trim();
  if (trimmedKey) {
    await invoke("provider_set_key", {
      profile,
      key: meta.env,
      value: value.keyValue,
    });
  }
  if (value.id === "openrouter") {
    const model = (value.model || "").trim().replace(/^openrouter\//, "");
    if (!model) return "OpenRouter key saved";
    await invoke("provider_add_openrouter_model", { profile, model });
    // Only seed the profile's model when it has none — replacing a key must not move a
    // running profile onto a different model behind the operator's back.
    if (!currentModel) {
      await invoke("set_config_field", {
        profile,
        key: "model",
        value: `openrouter/${model}`,
      });
      return `OpenRouter ${model} ready`;
    }
    return `${model} added to OpenRouter models`;
  }
  return `${meta.label} key saved`;
}

export default function ProviderPickerForm({
  value,
  onChange,
  configuredEnvs,
  configuredPreviews,
  savedOpenRouterModels = [],
  autoFocusFirstField = false,
  ollamaModelCount = 0,
  ollamaEndpointCount = 0,
  providerCatalog,
  chatgpt,
  signingIn = false,
}) {
  const [manualModel, setManualModel] = useState(false);
  const v = value ?? defaultProviderValue();
  const isOllama = v.id === "ollama";
  const isOpenRouter = v.id === "openrouter";
  const isChatGPT = v.id === CHATGPT_PLAN.id;
  const meta = !isOllama && !isChatGPT ? PAID_PROVIDERS.find((p) => p.id === v.id) : null;
  // A daemon that predates the sign-in sends no state for it, and the option stays out.
  const options = PROVIDER_OPTIONS.filter((p) => p.id !== CHATGPT_PLAN.id || chatgpt != null);

  function pick(id) {
    if (signingIn) return;
    if (id === "ollama") {
      onChange({ id: "ollama", name: "", url: "http://localhost:11434" });
    } else if (id === CHATGPT_PLAN.id) {
      onChange({ id });
    } else {
      onChange({ id, keyValue: "", model: id === "openrouter" ? "" : undefined });
    }
  }

  function patch(partial) {
    onChange({ ...v, ...partial });
  }

  return (
    <div className={styles.root}>
      <Dropdown
        trigger={{ label: options.find((p) => p.id === v.id)?.label ?? "Provider" }}
        direction="down"
        align="left"
        width={260}
        variant="field"
        fullWidth
      >
        {({ close }) => (
          <>
            {options.map((p) => (
              <Dropdown.Row
                key={p.id}
                onClick={() => {
                  pick(p.id);
                  close?.();
                }}
                caption={providerHint(p.id, {
                  configuredEnvs,
                  configuredPreviews,
                  providerCatalog,
                  ollamaModelCount,
                  ollamaEndpointCount,
                  chatgpt,
                })}
                active={p.id === v.id}
              >
                {p.label}
              </Dropdown.Row>
            ))}
          </>
        )}
      </Dropdown>

      {isChatGPT ? (
        chatgpt?.signed_in ? (
          <div className={styles.field}>
            <span className={styles.labelRow}>
              <Eyebrow>Account</Eyebrow>
              <ActionLink onClick={() => openExternal(CHATGPT_USAGE_URL).catch(() => {})}>Manage usage</ActionLink>
            </span>
            <Field value={chatgpt.email || "Signed in"} readOnly aria-label="ChatGPT account" />
          </div>
        ) : (
          <p className={styles.note}>
            {signingIn ? "Waiting for your browser…" : chatgpt?.plan_declined ? PLAN_DECLINED : "Opens your browser to sign in."}
          </p>
        )
      ) : isOllama ? (
        <div className={styles.grid}>
          <div className={styles.field}>
            <Eyebrow>Name</Eyebrow>
            <Field
              value={v.name ?? ""}
              onChange={(e) => patch({ name: e.target.value.toLowerCase() })}
              placeholder="local · home-gpu · cloud-a"
              spellCheck={false}
              autoFocus={autoFocusFirstField}
            />
          </div>
          <div className={styles.field}>
            <Eyebrow>URL</Eyebrow>
            <Field
              value={v.url ?? ""}
              onChange={(e) => patch({ url: e.target.value })}
              placeholder="http://localhost:11434"
              spellCheck={false}
            />
          </div>
        </div>
      ) : (
        <>
          <div className={styles.field}>
            <Eyebrow>API key</Eyebrow>
            <Field
              type="password"
              value={v.keyValue ?? ""}
              onChange={(e) => patch({ keyValue: e.target.value })}
              placeholder={
                configuredEnvs?.has?.(meta.env)
                  ? `current: ${configuredPreviews?.get?.(meta.env) ?? "•••"} (paste to replace)`
                  : "paste API key"
              }
              spellCheck={false}
              autoFocus={autoFocusFirstField}
            />
          </div>
          {isOpenRouter && (
            <div className={styles.field}>
              <span className={styles.labelRow}>
                <Eyebrow>Model</Eyebrow>
                {savedOpenRouterModels.length > 0 && (
                  <ActionLink onClick={() => {
                    setManualModel((on) => !on);
                    patch({ model: "" });
                  }}>
                    {manualModel ? "Pick from the list" : "Enter any slug"}
                  </ActionLink>
                )}
              </span>
              {manualModel || savedOpenRouterModels.length === 0 ? (
                <>
                  <Field
                    value={v.model ?? ""}
                    onChange={(e) => patch({ model: e.target.value })}
                    placeholder="provider/model-id (optional)"
                    spellCheck={false}
                    autoFocus={manualModel}
                  />
                </>
              ) : (
                <>
                  <Dropdown
                    trigger={{ label: v.model || "Known models" }}
                    direction="down"
                    align="left"
                    width={320}
                    variant="field"
                    fullWidth
                  >
                    {({ close }) => (
                      <>
                        {savedOpenRouterModels.map((m) => (
                          <Dropdown.Row
                            key={m}
                            onClick={() => {
                              patch({ model: m });
                              close?.();
                            }}
                            active={v.model === m}
                          >
                            {m}
                          </Dropdown.Row>
                        ))}
                      </>
                    )}
                  </Dropdown>
                </>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
