import { useDismissOnOutside } from "../hooks/useDismissOnOutside.js";
import Button from "../primitives/Button.jsx";
import { useCallback, useEffect, useRef, useState } from "react";
import { Dot, Tip, Mono, CheckIcon } from "../primitives/index.js";
import {
  applyPendingUpdate,
  checkForUpdates,
  describeUpdaterError,
  quitForUpdate,
  subscribeUpdater,
} from "../lib/updater.js";
import styles from "./VersionButton.module.css";

// eslint-disable-next-line no-undef
const APP_VERSION = typeof __APP_VERSION__ !== "undefined" ? __APP_VERSION__ : "0.0.0";

export default function VersionButton() {
  const [state, setState] = useState({
    checking: false,
    available: false,
    version: null,
    error: null,
    errorPhase: null,
    installing: false,
    phase: "idle",
    progress: null,
  });
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  // The tray's "Restart & install" runs the same install; the popover opens so the progress and any failure are visible.
  useEffect(
    () =>
      subscribeUpdater((next) => {
        setState(next);
        if (next.installing) setOpen(true);
      }),
    [],
  );

  useDismissOnOutside({ open, onClose: () => setOpen(false), wrapRef: ref });

  const onClick = useCallback(() => {
    setOpen(true);
    checkForUpdates();
  }, []);

  const triggerClass = state.available
    ? `mono ${styles.trigger} ${styles.triggerAvailable}`
    : `mono ${styles.trigger}`;

  return (
    <span ref={ref} className={styles.root}>
      <Tip text="Check for updates" side="up-r">
        <button
          type="button"
          onClick={onClick}
          className={triggerClass}
        >
          {APP_VERSION}
        </button>
      </Tip>
      {open && (
        <div className={`anim-pop ${styles.popover}`}>
          <VersionPanel
            state={state}
            current={APP_VERSION}
            onInstall={() => {
              applyPendingUpdate().catch(() => {});
            }}
            onClose={() => setOpen(false)}
          />
        </div>
      )}
    </span>
  );
}

function VersionPanel({ state, current, onInstall, onClose }) {
  if (state.checking) {
    return (
      <div className={`col ${styles.panel} ${styles.panelGap4}`}>
        <div className={`row row-gap ${styles.rowGap4}`}>
          <Dot pulse color="var(--ink-3)" />
          <span className={styles.label}>Checking for updates…</span>
        </div>
        <Mono className={styles.metaXs}>v{current}</Mono>
      </div>
    );
  }

  if (state.available) {
    const installed = state.errorPhase === "restart";
    const failed = state.error && (state.errorPhase === "install" || installed);
    const staleCheck = state.error && state.errorPhase === "check";
    const activity = !state.installing
      ? null
      : state.phase === "downloading"
        ? state.progress == null
          ? "Downloading…"
          : `Downloading… ${Math.round(state.progress * 100)}%`
        : state.phase === "installing"
          ? "Installing…"
          : "Restarting…";
    return (
      <div className={`col ${styles.panel} ${styles.panelGap5}`}>
        <div className={`col ${styles.colGap1}`}>
          <div className={`row row-gap ${styles.rowGap3}`}>
            <Dot color="var(--c-success)" pulse />
            <span className={styles.labelStrong}>Update available</span>
          </div>
          <Mono className={styles.metaSm}>
            {current} →{" "}
            <span className={styles.versionTo}>{state.version}</span>
          </Mono>
        </div>
        {activity ? (
          <div className={`row row-gap ${styles.rowGap3}`} aria-live="polite">
            <Dot pulse color="var(--ink-3)" />
            <span className={styles.label}>{activity}</span>
          </div>
        ) : null}
        {failed ? (
          <div className={`row row-gap ${styles.rowGap3}`} role="alert">
            <Dot color={installed ? "var(--c-success)" : "var(--c-danger)"} />
            <span className={styles.label}>{describeUpdaterError(state.error, state.errorPhase)}</span>
          </div>
        ) : staleCheck ? (
          <Mono className={styles.metaXs}>last check failed · {describeUpdaterError(state.error, "check")}</Mono>
        ) : null}
        <div className="row between">
          <button
            type="button"
            className="ds-alink"
            onClick={onClose}
          >
            Later
          </button>
          {installed ? (
            <Button
              type="button"
              variant="primary"
              className={styles.installBtn}
              onClick={() => { quitForUpdate(); }}
            >
              Quit Alpi
            </Button>
          ) : (
            <Button
              type="button"
              variant="primary"
              className={styles.installBtn}
              onClick={onInstall}
              disabled={state.installing}
            >
              {state.installing ? "Installing…" : failed ? "Try again" : "Restart & install"}
            </Button>
          )}
        </div>
      </div>
    );
  }

  if (state.error) {
    const friendly = describeUpdaterError(state.error, state.errorPhase ?? "check");
    return (
      <div className={`col ${styles.panel} ${styles.panelGap3}`}>
        <div className={`row row-gap ${styles.rowGap3}`}>
          <Dot color="var(--c-danger)" />
          <span className={styles.labelStrong}>{friendly}</span>
        </div>
        <Mono className={styles.metaSm}>v{current}</Mono>
      </div>
    );
  }

  return (
    <div className={`col ${styles.panel} ${styles.panelGap4}`}>
      <div className={`row row-gap ${styles.rowGap3}`}>
        <CheckIcon
          width={14}
          height={14}
          strokeWidth={2.2}
          className={styles.checkIcon}
        />
        <span className={styles.labelStrong}>You're up to date</span>
      </div>
      <Mono className={styles.metaSm}>v{current}</Mono>
    </div>
  );
}
