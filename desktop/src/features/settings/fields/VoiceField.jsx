import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../../primitives/Button.jsx";
import Chip from "../../../primitives/Chip.jsx";
import { useNotify } from "../../../primitives/Notification.jsx";
import { Row } from "../primitives.jsx";
import { VoicePicker } from "../../../primitives/index.js";
import { VOICE_SHORTLIST } from "../util.js";
import { playTts, previewPhraseFor } from "../../../lib/tts.js";
import styles from "../Settings.module.css";

export function VoiceField({ profile, onSaved }) {
  const notify = useNotify();
  const [busy, setBusy] = useState(null);
  const voiceId = profile.voice_id ?? "en-US-AriaNeural";
  const autoRead = !!profile.voice_auto_read;

  async function setAutoRead(enabled) {
    setBusy("auto_read");
    try {
      await invoke("voice_set_auto_read", { profile: profile.name, enabled });
      await onSaved?.();
    } catch (e) {
      notify({ message: `auto-read: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setBusy(null);
    }
  }

  async function pickVoice(id) {
    setBusy("voice");
    try {
      await invoke("voice_set_voice", { profile: profile.name, voiceId: id });
      await onSaved?.();
    } catch (e) {
      notify({ message: `voice: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setBusy(null);
    }
  }

  async function testVoice() {
    setBusy("test");
    try {
      await playTts({
        key: `voice-preview:${voiceId}`,
        profile: profile.name,
        voice: voiceId,
        text: previewPhraseFor(voiceId),
        raw: true,
      });
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <Row label="voice">
        <span className={styles.inlineRow}>
          <VoicePicker
            voices={VOICE_SHORTLIST}
            current={voiceId}
            accent={profile.accent}
            onChange={(id) => {
              if (id !== voiceId) pickVoice(id);
            }}
          />
          <Button
            size="sm"
            onClick={testVoice}
            disabled={!!busy}
            loading={busy === "test"}
            title="play a localized greeting in this voice"
          >
            Test
          </Button>
        </span>
      </Row>
      <Row label="auto-read">
        <span className={styles.inlineRow}>
          <Chip
            state={autoRead ? "on" : "off"}
            tooltip="reads every agent reply aloud as it arrives — never your messages"
          >
            {autoRead ? "on" : "off"}
          </Chip>
          <Button
            size="sm"
            onClick={() => setAutoRead(!autoRead)}
            disabled={!!busy}
            loading={busy === "auto_read"}
          >
            {autoRead ? "Disable" : "Enable"}
          </Button>
        </span>
      </Row>
    </>
  );
}
