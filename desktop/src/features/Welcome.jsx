import { useState } from "react";
import { Button, Fold, IconBtn, Mono } from "../primitives/index.js";
import { CopyIcon } from "../primitives/icons.jsx";
import StepLadder from "../primitives/StepLadder.jsx";
import ConnectElsewhere from "../primitives/ConnectElsewhere.jsx";
import { copyText } from "../lib/clipboard.js";
import { INSTALL_COMMANDS, START_COMMAND } from "../../../common/onboarding.mjs";
import styles from "./Welcome.module.css";

const FIRST_RUN_HINT_KEY = "alpi.firstRunHint.v1";

export function firstRunHintSeen() {
  try {
    return localStorage.getItem(FIRST_RUN_HINT_KEY) === "seen";
  } catch {
    return true;
  }
}

export function markFirstRunHintSeen() {
  try {
    localStorage.setItem(FIRST_RUN_HINT_KEY, "seen");
  } catch {}
}

export function FirstRunHint({ onDismiss }) {
  return (
    <aside className={styles.hint}>
      <div className={styles.hintBody}>
        <strong className={styles.hintTitle}>This is alpi on this computer</strong>
        <span className={styles.hintText}>To use it from a phone: Settings → Connections → New connection, then scan the code.</span>
      </div>
      <Button variant="secondary" size="sm" onClick={onDismiss}>Got it</Button>
    </aside>
  );
}

function Command({ value }) {
  return (
    <div className={styles.command}>
      <Mono className={styles.commandText}>{value}</Mono>
      <IconBtn tip="Copy" aria-label={`Copy ${value}`} onClick={() => copyText(value)}>
        <CopyIcon />
      </IconBtn>
    </div>
  );
}

export { ConnectElsewhere };

export default function Welcome({ localState, phase = "idle", error = null, onStart, onCheckAgain, onConnect }) {
  const [elsewhere, setElsewhere] = useState(false);

  if (phase === "starting") {
    return (
      <section className={styles.welcome} aria-live="polite">
        <Fold fold="alpaca" size={40} />
        <h1 className={styles.title}>Starting alpi…</h1>
        <StepLadder
          steps={[
            { id: "asked", state: "done", label: "Start requested" },
            { id: "answer", state: "now", label: "Waiting for alpi to answer" },
          ]}
        />
      </section>
    );
  }

  if (phase === "failed") {
    return (
      <section className={styles.welcome}>
        <Fold fold="alpaca" size={40} />
        <h1 className={styles.title}>alpi didn't start</h1>
        {error ? <pre className={styles.error}>{error}</pre> : null}
        <p className={styles.sub}>Start it from a terminal to see what it says:</p>
        <Command value={START_COMMAND} />
        <div className={styles.actions}>
          <Button variant="secondary" onClick={onStart}>Retry</Button>
          <Button variant="ghost" onClick={() => setElsewhere(true)}>Connect to another computer</Button>
        </div>
        {elsewhere ? <ConnectElsewhere onConnect={onConnect} autoFocus /> : null}
      </section>
    );
  }

  if (localState === "stopped") {
    return (
      <section className={styles.welcome}>
        <Fold fold="alpaca" size={40} />
        <h1 className={styles.title}>alpi is installed but not running</h1>
        <p className={styles.sub}>Start it here, or connect to an alpi that runs somewhere else.</p>
        <div className={styles.actions}>
          <Button variant="primary" onClick={onStart}>Start alpi</Button>
          <Button variant="ghost" onClick={() => setElsewhere(true)}>Connect to another computer</Button>
        </div>
        {elsewhere ? <ConnectElsewhere onConnect={onConnect} autoFocus /> : null}
      </section>
    );
  }

  const unsupported = localState === "unsupported";
  return (
    <section className={styles.welcome}>
      <Fold fold="alpaca" size={40} />
      <h1 className={styles.title}>{unsupported ? "Connect to alpi" : "Set up alpi"}</h1>
      <p className={styles.sub}>
        {unsupported
          ? "alpi does not run on this system yet, so connect to one that runs elsewhere."
          : "No alpi on this computer yet. Both paths end in the same window."}
      </p>
      <div className={styles.choices}>
        {unsupported ? null : (
          <div className={styles.choice}>
            <h2 className={styles.choiceTitle}>Run alpi here</h2>
            <p className={styles.choiceSub}>Install it, then pick a model in setup. This window notices when it starts.</p>
            {INSTALL_COMMANDS.map((c) => <Command key={c} value={c} />)}
            <div className={styles.actions}>
              <Button variant="secondary" onClick={onCheckAgain}>Check again</Button>
            </div>
          </div>
        )}
        <div className={styles.choice}>
          <h2 className={styles.choiceTitle}>Connect to alpi elsewhere</h2>
          <p className={styles.choiceSub}>Paste the link made on the computer that runs it.</p>
          <ConnectElsewhere onConnect={onConnect} />
        </div>
      </div>
    </section>
  );
}
