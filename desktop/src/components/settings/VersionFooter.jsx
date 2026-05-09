import { useEffect, useState } from "react";
import { getVersion } from "@tauri-apps/api/app";
import { useNotify } from "../../primitives/Notification.jsx";
import {
  applyPendingUpdate,
  checkForUpdates,
  subscribeUpdater,
} from "../../lib/updater.js";
import styles from "../Settings.module.css";

export default function VersionFooter() {
  const [version, setVersion] = useState("");
  const [updater, setUpdater] = useState({
    checking: false,
    available: false,
    version: null,
    error: null,
    installing: false,
  });
  const notify = useNotify();

  useEffect(() => {
    getVersion().then(setVersion).catch(() => setVersion("?"));
  }, []);

  useEffect(() => subscribeUpdater(setUpdater), []);

  async function checkNow() {
    if (updater.checking || updater.installing) return;
    try {
      const next = await checkForUpdates();
      if (next.available && next.version) {
        notify({
          message: `Update available: ${next.version}`,
          variant: "success",
          duration: 3500,
        });
      } else if (!next.error) {
        notify({ message: "You're on the latest version.", variant: "success" });
      }
    } catch (e) {
      notify({
        message: `Update check failed: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    }
  }

  async function installNow() {
    if (!updater.available || updater.installing) return;
    try {
      notify({
        message: `Installing ${updater.version}… app will restart when ready.`,
        variant: "success",
        duration: 4000,
      });
      await applyPendingUpdate();
    } catch (e) {
      notify({
        message: `Update install failed: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    }
  }

  if (!version) return null;
  return (
    <div className={styles.asideFooter}>
      <span>Alpi {version}</span>
      <span>·</span>
      <button
        type="button"
        className={styles.asideFooterButton}
        onClick={checkNow}
        disabled={updater.checking || updater.installing}
      >
        {updater.checking ? "checking…" : "check for updates"}
      </button>
      {updater.available && updater.version && (
        <>
          <span>·</span>
          <button
            type="button"
            className={styles.asideFooterButton}
            onClick={installNow}
            disabled={updater.installing}
          >
            {updater.installing
              ? "installing…"
              : `install ${updater.version}`}
          </button>
        </>
      )}
    </div>
  );
}
