import { useEffect, useState } from "react";
import { subscribeTts, clearTtsQueue } from "../lib/tts.js";
import WaveBars from "./WaveBars.jsx";
import Tip from "./Tip.jsx";
import styles from "./SoundWave.module.css";

export default function SoundWave({ accent }) {
  const [state, setState] = useState(null);

  useEffect(() => {
    return subscribeTts((s) => {
      if (s?.kind === "playing" || s?.kind === "loading") setState(s);
      else setState(null);
    });
  }, []);

  if (!state) return null;

  return (
    <Tip text="Stop read-aloud" side="r">
      <button
        type="button"
        className={styles.wave}
        onClick={clearTtsQueue}
        aria-label="stop read-aloud"
      >
        <WaveBars accent={state.accent || accent} active />
      </button>
    </Tip>
  );
}
