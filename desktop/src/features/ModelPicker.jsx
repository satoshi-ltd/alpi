import { useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import DsModelPicker from "../primitives/ModelPicker.jsx";

export default function ModelPicker({
  profile,
  models,
  defaultModel,
  value,
  onChange,
  accent,
  mode = "override",
  variant = "ghost",
}) {
  const [ollamaModels, setOllamaModels] = useState([]);
  const [ollamaLoaded, setOllamaLoaded] = useState(false);

  useEffect(() => {
    setOllamaModels([]);
    setOllamaLoaded(false);
  }, [profile]);

  useEffect(() => {
    if (!profile || ollamaLoaded) return;
    let cancelled = false;
    invoke("ollama_models", { profile })
      .then((rows) => {
        if (cancelled) return;
        setOllamaModels(Array.isArray(rows) ? rows : []);
        setOllamaLoaded(true);
      })
      .catch(() => {
        if (!cancelled) setOllamaLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [profile, ollamaLoaded]);

  const groupedModels = useMemo(() => {
    const seen = new Set();
    const groups = {};
    for (const m of [...(models ?? []), ...ollamaModels]) {
      if (!m || seen.has(m)) continue;
      seen.add(m);
      const i = m.indexOf("/");
      const provider = i === -1 ? "other" : m.slice(0, i);
      const label = i === -1 ? m : m.slice(i + 1);
      if (!groups[provider]) groups[provider] = [];
      groups[provider].push({ id: m, label });
    }
    return groups;
  }, [models, ollamaModels]);

  const active = value ?? defaultModel ?? null;
  const flatCount = Object.values(groupedModels).reduce(
    (n, list) => n + list.length,
    0,
  );
  if (mode === "override" && flatCount <= 1) return null;
  if (flatCount === 0) return null;

  return (
    <DsModelPicker
      currentModel={active}
      accent={accent ?? null}
      models={groupedModels}
      mode={mode}
      variant={variant}
      onPick={(id) => {
        if (mode === "default") onChange?.(id);
        else onChange?.(id === defaultModel ? null : id);
      }}
    />
  );
}
