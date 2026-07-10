import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import ModelPicker from "../../ModelPicker.jsx";

export function ModelField({ profile, value, onChange, onLoadingChange = null, onOllamaErrors = null }) {
  const [ollama, setOllama] = useState([]);
  useEffect(() => {
    let cancelled = false;
    onLoadingChange?.(true);
    invoke("ollama_models", { profile: profile.name })
      .then((envelope) => {
        if (cancelled) return;
        if (Array.isArray(envelope)) {
          setOllama(envelope);
          onOllamaErrors?.([]);
        } else {
          setOllama(Array.isArray(envelope?.models) ? envelope.models : []);
          onOllamaErrors?.(Array.isArray(envelope?.errors) ? envelope.errors : []);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setOllama([]);
          onOllamaErrors?.([]);
        }
      })
      .finally(() => { if (!cancelled) onLoadingChange?.(false); });
    return () => {
      cancelled = true;
      onLoadingChange?.(false);
    };
  }, [profile.name, onLoadingChange, onOllamaErrors]);

  const merged = [...(profile.models ?? []), ...ollama];
  return (
    <ModelPicker
      profile={profile.name}
      models={merged}
      defaultModel={value}
      value={value}
      accent={profile.accent ?? null}
      mode="default"
      variant="field"
      onChange={(id) => onChange?.(id)}
    />
  );
}
