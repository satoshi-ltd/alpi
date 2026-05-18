import { invoke } from "@tauri-apps/api/core";
import { Chip, Eyebrow } from "../../primitives/index.js";
import { PAID_PROVIDERS } from "./util.js";
import styles from "./ProviderPickerForm.module.css";

const PROVIDER_OPTIONS = [
  { id: "ollama", label: "Ollama" },
  ...PAID_PROVIDERS,
];

export function defaultProviderValue() {
  return { id: "ollama", name: "", url: "http://localhost:11434" };
}

export function isProviderValueValid(value, { configuredEnvs } = {}) {
  if (!value) return false;
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
  if (value.id === "openrouter") {
    const model = (value.model || "").trim().replace(/^openrouter\//, "");
    return keyOk && model.length > 0;
  }
  return keyOk;
}

export async function applyProvider(profile, value) {
  if (value.id === "ollama") {
    const name = value.name.trim();
    const url = value.url.trim().replace(/\/$/, "");
    await invoke("provider_add_ollama", { profile, name, url });
    return `Ollama @${name} added`;
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
    const model = value.model.trim().replace(/^openrouter\//, "");
    if (model) {
      await invoke("provider_add_openrouter_model", { profile, model });
    }
    return `OpenRouter ${model} ready`;
  }
  return `${meta.label} key saved`;
}

export default function ProviderPickerForm({
  value,
  onChange,
  configuredEnvs,
  savedOpenRouterModels = [],
  autoFocusFirstField = false,
}) {
  const v = value ?? defaultProviderValue();
  const isOllama = v.id === "ollama";
  const isOpenRouter = v.id === "openrouter";
  const meta = !isOllama ? PAID_PROVIDERS.find((p) => p.id === v.id) : null;

  function pick(id) {
    if (id === "ollama") {
      onChange({ id: "ollama", name: "", url: "http://localhost:11434" });
    } else {
      onChange({ id, keyValue: "", model: id === "openrouter" ? "" : undefined });
    }
  }

  function patch(partial) {
    onChange({ ...v, ...partial });
  }

  return (
    <div className={styles.root}>
      <div className={styles.chips}>
        {PROVIDER_OPTIONS.map((p) => (
          <Chip
            key={p.id}
            state={v.id === p.id ? "on" : "off"}
            onClick={() => pick(p.id)}
          >
            {p.label}
          </Chip>
        ))}
      </div>

      {isOllama ? (
        <div className={styles.grid}>
          <div className={styles.field}>
            <Eyebrow>NAME</Eyebrow>
            <input
              className={styles.input}
              value={v.name ?? ""}
              onChange={(e) => patch({ name: e.target.value.toLowerCase() })}
              placeholder="local · home-gpu · cloud-a"
              spellCheck={false}
              autoFocus={autoFocusFirstField}
            />
          </div>
          <div className={styles.field}>
            <Eyebrow>URL</Eyebrow>
            <input
              className={styles.input}
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
            <Eyebrow>{meta.env}</Eyebrow>
            <input
              className={styles.input}
              type="password"
              value={v.keyValue ?? ""}
              onChange={(e) => patch({ keyValue: e.target.value })}
              placeholder={
                configuredEnvs?.has?.(meta.env)
                  ? "(replace existing key)"
                  : "paste API key"
              }
              spellCheck={false}
              autoFocus={autoFocusFirstField}
            />
          </div>
          {isOpenRouter && (
            <div className={styles.field}>
              <Eyebrow>MODEL</Eyebrow>
              <input
                className={styles.input}
                value={v.model ?? ""}
                onChange={(e) => patch({ model: e.target.value })}
                placeholder="provider/model-id"
                spellCheck={false}
              />
              {savedOpenRouterModels.length > 0 && (
                <div className={styles.modelChips}>
                  {savedOpenRouterModels.map((m) => (
                    <Chip
                      key={m}
                      size="sm"
                      state={v.model === m ? "on" : "off"}
                      onClick={() => patch({ model: m })}
                    >
                      {m}
                    </Chip>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
