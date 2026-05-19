import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import ModelPicker from "../../ModelPicker.jsx";
import styles from "../Settings.module.css";

export function ModelField({ profile, value, onChange }) {
  const [ollama, setOllama] = useState([]);
  const [ollamaErrors, setOllamaErrors] = useState([]);
  useEffect(() => {
    invoke("ollama_models", { profile: profile.name })
      .then((envelope) => {
        if (Array.isArray(envelope)) {
          setOllama(envelope);
          setOllamaErrors([]);
        } else {
          setOllama(Array.isArray(envelope?.models) ? envelope.models : []);
          setOllamaErrors(Array.isArray(envelope?.errors) ? envelope.errors : []);
        }
      })
      .catch(() => {
        setOllama([]);
        setOllamaErrors([]);
      });
  }, [profile.name]);

  const merged = [...(profile.models ?? []), ...ollama];
  return (
    <>
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
      {ollamaErrors.length > 0 && (
        <span className={styles.warnBlock}>
          {ollamaErrors.map((e) => (
            <span key={e.name} className={styles.warnLine}>
              <strong>ollama/{e.name}</strong> · <span className={styles.mono}>{e.url}</span>{" "}
              — {e.detail}
            </span>
          ))}
        </span>
      )}
    </>
  );
}
