import { useCallback, useEffect, useRef, useState } from "react";
import { Activity, Dot, Tip, Mono, CheckIcon } from "../primitives/index.js";
import {
  applyPendingUpdate,
  checkForUpdates,
  subscribeUpdater,
} from "../lib/updater.js";
import styles from "./VersionButton.module.css";

// eslint-disable-next-line no-undef
const APP_VERSION = typeof __APP_VERSION__ !== "undefined" ? __APP_VERSION__ : "0.0.0";

function friendlyUpdaterError(raw) {
  const s = String(raw || "").toLowerCase();
  if (s.includes("platform") || s.includes("fallback")) {
    return "No build available for your platform yet";
  }
  if (s.includes("network") || s.includes("fetch") || s.includes("dns") || s.includes("timeout")) {
    return "Couldn't reach update server";
  }
  if (s.includes("signature") || s.includes("signing")) {
    return "Update signature check failed";
  }
  return "Couldn't check for updates";
}

export default function VersionButton() {
  const [state, setState] = useState({
    checking: false,
    available: false,
    version: null,
    error: null,
    installing: false,
  });
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => subscribeUpdater(setState), []);

  useEffect(() => {
    if (!open) return undefined;
    function onDoc(e) {
      if (!ref.current?.contains(e.target)) setOpen(false);
    }
    function onKey(e) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

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
          <Activity size="md" />
          <span className={styles.label}>Checking for updates…</span>
        </div>
        <Mono className={styles.metaXs}>v{current}</Mono>
      </div>
    );
  }

  if (state.available) {
    return (
      <div className={`col ${styles.panel} ${styles.panelGap5}`}>
        <div className={`col ${styles.colGap1}`}>
          <div className={`row row-gap ${styles.rowGap3}`}>
            <Dot color="var(--c-success)" size={8} pulse />
            <span className={styles.labelStrong}>Update available</span>
          </div>
          <Mono className={styles.metaSm}>
            {current} →{" "}
            <span className={styles.versionTo}>{state.version}</span>
          </Mono>
        </div>
        <div className="row between">
          <button
            type="button"
            className="ds-alink"
            onClick={onClose}
          >
            Later
          </button>
          <button
            type="button"
            className={`ds-btn ds-btn-primary ${styles.installBtn}`}
            onClick={onInstall}
            disabled={state.installing}
          >
            {state.installing ? "Installing…" : "Restart & install"}
          </button>
        </div>
      </div>
    );
  }

  if (state.error) {
    const friendly = friendlyUpdaterError(state.error);
    return (
      <div className={`col ${styles.panel} ${styles.panelGap3}`}>
        <div className={`row row-gap ${styles.rowGap3}`}>
          <Dot color="var(--c-danger)" size={8} />
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
