import { invoke } from "@tauri-apps/api/core";
import Button from "../../../primitives/Button.jsx";
import { useNotify } from "../../../primitives/Notification.jsx";
import ModelPicker from "../../ModelPicker.jsx";
import { ReasoningEffortField } from "./ReasoningEffortField.jsx";
import styles from "../Settings.module.css";

export function TierField({ profile, name, onSaved }) {
  const notify = useNotify();
  const tier = profile.tiers?.[name] ?? { model: "", effort: "", reasoning_supported: false };
  const fail = (e) =>
    notify({ message: `${name} tier: ${String(e)}`, variant: "error", duration: 4000 });
  const persist = (key, value) =>
    invoke("set_config_field", { profile: profile.name, key, value })
      .then(() => onSaved?.())
      .catch(fail);
  const clear = () =>
    invoke("unset_config_field", { profile: profile.name, key: `tiers.${name}` })
      .then(() => onSaved?.())
      .catch(fail);
  return (
    <span className={styles.inlineRow}>
      <ModelPicker
        profile={profile.name}
        models={profile.models ?? []}
        defaultModel={tier.model}
        value={tier.model}
        accent={profile.accent ?? null}
        mode="default"
        variant="field"
        onChange={(id) => persist(`tiers.${name}.model`, id)}
      />
      {tier.model ? (
        <>
          {tier.reasoning_supported && (
            <ReasoningEffortField
              value={tier.effort}
              onChange={(v) => persist(`tiers.${name}.effort`, v)}
            />
          )}
          <Button size="sm" onClick={clear}>
            Clear
          </Button>
        </>
      ) : (
        <span className={styles.muted}>uses main model</span>
      )}
    </span>
  );
}
