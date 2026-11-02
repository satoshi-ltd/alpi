import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../../primitives/Button.jsx";
import Icon from "../../../primitives/Icon.jsx";
import { useNotify } from "../../../primitives/Notification.jsx";
import Tip from "../../../primitives/Tip.jsx";
import { modelLabel } from "../../../lib/modelLabel.js";
import ModelPicker from "../../ModelPicker.jsx";
import {
  FALLBACK_HINT,
  FALLBACK_KEY,
  MAX_FALLBACKS,
  addFallback,
  fallbackList,
  moveFallback,
  removeFallback,
} from "../../../../../common/fallbackModels.mjs";
import styles from "../Settings.module.css";

export function FallbackModelsField({ profile, onSaved }) {
  const notify = useNotify();
  const [busy, setBusy] = useState(false);
  const list = fallbackList(profile);
  const main = profile.model ?? "";
  const fail = (e) =>
    notify({ message: `fallback models: ${String(e)}`, variant: "error", duration: 4000 });
  const persist = (next) => {
    if (busy || next === list) return;
    setBusy(true);
    return invoke("set_config_field", {
      profile: profile.name,
      key: FALLBACK_KEY,
      value: JSON.stringify(next),
    })
      .then(() => Promise.resolve(onSaved?.()).catch(() => null), fail)
      .finally(() => setBusy(false));
  };

  return (
    <span className={styles.stackedField}>
      {list.length === 0 && <span className={styles.muted}>none</span>}
      {list.map((model, i) => (
        <span key={model} className={styles.inlineRow}>
          <Tip text={model} side="up">
            <span className={styles.mono}>{`${i + 1} · ${modelLabel(model)}`}</span>
          </Tip>
          <Button
            size="sm"
            variant="ghost"
            icon={<Icon name="chevron-up" size="sm" />}
            tip={`Move ${modelLabel(model)} up`}
            disabled={busy || i === 0}
            onClick={() => persist(moveFallback(list, i, -1))}
          />
          <Button
            size="sm"
            variant="ghost"
            icon={<Icon name="chevron-down" size="sm" />}
            tip={`Move ${modelLabel(model)} down`}
            disabled={busy || i === list.length - 1}
            onClick={() => persist(moveFallback(list, i, 1))}
          />
          <Button
            size="sm"
            variant="ghost"
            icon={<Icon name="x" size="sm" />}
            tip={`Remove ${modelLabel(model)}`}
            disabled={busy}
            onClick={() => persist(removeFallback(list, i))}
          />
        </span>
      ))}
      <span className={styles.inlineRow}>
        {list.length >= MAX_FALLBACKS ? (
          <span className={styles.muted}>{`${MAX_FALLBACKS} is the most a profile can list.`}</span>
        ) : (
          <ModelPicker
            profile={profile.name}
            models={profile.models ?? []}
            exclude={[main, ...list]}
            placeholder="Add"
            value={null}
            defaultModel={null}
            accent={profile.accent ?? null}
            mode="default"
            variant="field"
            onChange={(id) => persist(addFallback(list, id, main))}
          />
        )}
        <span className={styles.muted}>{FALLBACK_HINT}</span>
      </span>
    </span>
  );
}
