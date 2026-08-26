import { invoke } from "@tauri-apps/api/core";
import Button from "../../../primitives/Button.jsx";
import { useNotify } from "../../../primitives/Notification.jsx";
import ModelPicker from "../../ModelPicker.jsx";
import styles from "../Settings.module.css";

export function VisionModelField({ profile, onSaved }) {
  const notify = useNotify();
  const model = profile.vision_model ?? "";
  const fail = (e) =>
    notify({ message: `vision model: ${String(e)}`, variant: "error", duration: 4000 });
  const persist = (value) =>
    invoke("set_config_field", {
      profile: profile.name,
      key: "tools.read_image.model",
      value,
    })
      .then(() => onSaved?.())
      .catch(fail);

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
