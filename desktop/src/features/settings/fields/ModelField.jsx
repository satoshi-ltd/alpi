import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import ModelPicker from "../../ModelPicker.jsx";

export function ModelField({ profile, value, onChange }) {
  const [ollama, setOllama] = useState([]);
  useEffect(() => {
    invoke("ollama_models", { profile: profile.name })
      .then((list) => setOllama(Array.isArray(list) ? list : []))
      .catch(() => setOllama([]));
  }, [profile.name]);

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
