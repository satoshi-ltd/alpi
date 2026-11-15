import { invoke } from "@tauri-apps/api/core";
import Button from "../../../primitives/Button.jsx";
import { useNotify } from "../../../primitives/Notification.jsx";
import ModelPicker from "../../ModelPicker.jsx";
import { saveOptimistic } from "../../../lib/optimisticProfiles.js";
import styles from "../Settings.module.css";

export function VisionModelField({ profile, connectionId = null, onSaved }) {
  const notify = useNotify();
  const model = profile.vision_model ?? "";
  const fail = (e) =>
    notify({ message: `vision model: ${String(e)}`, variant: "error", duration: 4000 });
  const persist = (value) =>
    saveOptimistic({
      connectionId,
      name: profile.name,
      patch: { vision_model: value },
      run: () => invoke("set_config_field", {
        profile: profile.name,
        key: "tools.read_image.model",
        value,
        connectionId,
      }),
      onFailed: fail,
      refresh: onSaved,
    }).then(({ latest }) => {
      if (latest) onSaved?.();
    }, () => {});

  return (
    <span className={styles.inlineRow}>
      <ModelPicker
        profile={profile.name}
        models={profile.models ?? []}
        defaultModel={model}
        value={model}
        accent={profile.accent ?? null}
        mode="default"
        variant="field"
        onChange={persist}
      />
      {model ? (
        <Button size="sm" onClick={() => persist("")}>
          Clear
        </Button>
      ) : (
        <span className={styles.muted}>read_image uses main model</span>
      )}
    </span>
  );
}
