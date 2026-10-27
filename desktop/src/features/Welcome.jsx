import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Button, DisplayHeading, Fold, IconBtn, Mono } from "../primitives/index.js";
import { BusyMark } from "../primitives/Busy.jsx";
import { useBusyVisible } from "../lib/useBusyVisible.js";
import { CopyIcon } from "../primitives/icons.jsx";
import StepLadder from "../primitives/StepLadder.jsx";
import ConnectElsewhere from "../primitives/ConnectElsewhere.jsx";
import { copyText } from "../lib/clipboard.js";
import { ALPACA_FOLD, FOLD_SIZES, foldPolygons } from "../../../common/folds.mjs";
import { START_COMMAND } from "../../../common/onboarding.mjs";
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

const LOCAL_EVER_ONLINE_KEY = "alpi.localEverOnline.v1";

export function localEverOnlineSeen() {
  try {
    return localStorage.getItem(LOCAL_EVER_ONLINE_KEY) === "seen";
  } catch {
    return false;
  }
}

export function markLocalEverOnline() {
  try {
    localStorage.setItem(LOCAL_EVER_ONLINE_KEY, "seen");
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

const INK = (() => {
  const points = foldPolygons(ALPACA_FOLD, "#808080", FOLD_SIZES.hero).flatMap((facet) => facet.points);
  const scale = FOLD_SIZES.hero / 100;
  return {
    left: Math.min(...points.map(([x]) => x)) * scale,
    top: Math.min(...points.map(([, y]) => y)) * scale,
    bottom: (100 - Math.max(...points.map(([, y]) => y))) * scale,
  };
})();
const MARK_MARGIN = `-${INK.top}px 0 -${INK.bottom}px -${INK.left}px`;

function Mark({ busy = false }) {
  const waiting = useBusyVisible(busy);
  return (
    <span className={styles.mark} style={{ width: FOLD_SIZES.hero, height: FOLD_SIZES.hero, margin: MARK_MARGIN }} aria-hidden={busy ? "true" : undefined}>
      {busy && waiting ? <BusyMark size={FOLD_SIZES.hero} /> : <Fold fold={ALPACA_FOLD} size={FOLD_SIZES.hero} />}
    </span>
  );
}

export function WelcomeFrame() {
  return (
    <section className={styles.welcome}>
      <div className={styles.strip} data-drag />
    </section>
  );
}

function Screen({ busy = false, title, sub = null, live = null, busyState = false, children }) {
  return (
    <section className={styles.welcome} aria-live={live || undefined} aria-busy={busyState || undefined}>
      <div className={styles.strip} data-drag />
      <div className={styles.scroll}>
        <div className={styles.column}>
          <Mark busy={busy} />
          <DisplayHeading hero className={styles.title} style={{ marginTop: "var(--sp-24)" }}>{title}</DisplayHeading>
          {sub ? <p className={styles.sub}>{sub}</p> : null}
          {children}
        </div>
      </div>
    </section>
  );
}

function Command({ value }) {
  return (
    <div className={styles.command}>
      <Mono className={styles.commandText}>{value}</Mono>
      <IconBtn size="sm" tip="Copy" aria-label={`Copy ${value}`} onClick={() => copyText(value)}>
        <CopyIcon />
      </IconBtn>
    </div>
  );
}

function Log({ text }) {
  const ref = useRef(null);
  useLayoutEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [text]);
  return <pre ref={ref} className={styles.log} role="region" aria-label="Error output" tabIndex={0}>{text}</pre>;
}

function Actions({ primary, onPrimary, ghosts }) {
  const ref = useRef(null);
  useEffect(() => {
    ref.current?.focus({ preventScroll: true });
  }, []);
  return (
    <div className={styles.actions}>
      {primary ? <Button ref={ref} variant="primary" size="lg" className={styles.primary} onClick={onPrimary}>{primary}</Button> : null}
      {ghosts.map(({ label, onClick }) => (
        <Button key={label} variant="ghost" size="lg" onClick={onClick}>{label}</Button>
      ))}
    </div>
  );
}

export { ConnectElsewhere };

const CONNECT_SUB = "Paste the link made on the computer that runs it.";

export default function Welcome({ localState, phase = "idle", error = null, onStart, onInstall, onCheckAgain, onConnect }) {
  const [elsewhere, setElsewhere] = useState(false);
  const [draft, setDraft] = useState("");
  const toForm = { label: "Connect to another computer", onClick: () => setElsewhere(true) };
  const unsupported = localState === "unsupported";
  const working = phase === "installing" || phase === "starting";

  if (!working && (elsewhere || unsupported)) {
    return (
      <Screen title="Connect to alpi" sub={unsupported ? "alpi does not run on this system yet, so connect to one that runs elsewhere." : CONNECT_SUB}>
        <ConnectElsewhere onConnect={onConnect} initialLink={draft} onLinkChange={setDraft} autoFocus onBack={unsupported ? null : () => setElsewhere(false)} />
      </Screen>
    );
  }

  if (phase === "installing") {
    return (
      <Screen busy busyState live="polite" title="Installing alpi…" sub="Downloading uv, Python and alpi. This can take a few minutes. Keep this window open.">
        <div className={styles.facts}>
          <StepLadder steps={[
            { id: "install", state: "now", label: "Installing alpi and its runtime" },
            { id: "start", state: "todo", label: "Start alpi" },
          ]} />
        </div>
      </Screen>
    );
  }

  if (phase === "starting") {
    return (
      <Screen busy live="polite" title="Starting alpi…">
        <div className={styles.facts}>
          <StepLadder
            steps={[
              { id: "asked", state: "done", label: "Start requested" },
              { id: "answer", state: "now", label: "Waiting for alpi to answer" },
            ]}
          />
        </div>
      </Screen>
    );
  }

  if (phase === "failed" || phase === "install-failed") {
    const install = phase === "install-failed";
    return (
      <Screen title={install ? "alpi couldn't be installed" : "alpi didn't start"} sub={!error && install ? "Check your internet connection, then try again." : null}>
        {error ? <Log text={error} /> : null}
        {install ? null : (
          <>
            <p className={`${styles.sub} ${error ? styles.below : ""}`}>Start it from a terminal to see what it says:</p>
            <Command value={START_COMMAND} />
          </>
        )}
        <Actions primary="Retry" onPrimary={install ? onInstall : onStart} ghosts={[toForm]} />
      </Screen>
    );
  }

  if (localState === "stopped") {
    return (
      <Screen title="alpi is installed but not running" sub="Start it here, or connect to an alpi that runs somewhere else.">
        <Actions primary="Start alpi" onPrimary={onStart} ghosts={[toForm]} />
      </Screen>
    );
  }

  return (
    <Screen title="Set up alpi" sub="alpi runs your agents on this computer. Installing it needs an internet connection.">
      <Actions primary="Install and start alpi" onPrimary={onInstall} ghosts={[{ label: "Check again", onClick: onCheckAgain }, toForm]} />
    </Screen>
  );
}
