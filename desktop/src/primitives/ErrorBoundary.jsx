import React from "react";
import AlpiSilhouette from "./AlpiSilhouette.jsx";
import { clearCrash, describeError, formatCrash, recordCrash } from "../lib/crashLog.js";
import styles from "./ErrorBoundary.module.css";

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      entry: props.initialEntry || null,
      recovery: Boolean(props.initialEntry),
      copyStatus: "idle",
    };
  }

  static getDerivedStateFromError(error) {
    return {
      entry: { at: new Date().toISOString(), phase: "render", ...describeError(error) },
      recovery: false,
      copyStatus: "idle",
    };
  }

  componentDidCatch(error, info) {
    const entry = recordCrash(error, {
      phase: "render",
      componentStack: String(info?.componentStack || "").slice(0, 4000),
      url: typeof window !== "undefined" ? window.location?.href : "",
    });
    this.setState({ entry, recovery: false, copyStatus: "idle" });
    console.error("desktop render crash", error, info?.componentStack);
  }

  copy = async () => {
    try {
      await navigator.clipboard.writeText(formatCrash(this.state.entry));
      this.setState({ copyStatus: "copied" });
    } catch {
      this.setState({ copyStatus: "failed" });
    }
  };

  continue = () => {
    clearCrash();
    this.setState({ entry: null, recovery: false, copyStatus: "idle" });
  };

  render() {
    const { entry, recovery, copyStatus } = this.state;
    if (!entry) return this.props.children;
    return (
      <div className={styles.wrap}>
        <div className={styles.card}>
          <AlpiSilhouette className={styles.mark} />
          <div className={styles.heading}>
            <h1 className={styles.title}>
              {recovery ? "Alpi recovered from a crash" : "Something broke on screen"}
            </h1>
            <p className={styles.lede}>
              {recovery
                ? "The interface restarted. The daemon and running agents continued separately."
                : "The interface stopped rendering. The daemon and running agents continue separately; unsaved interface changes may need to be entered again."}
            </p>
          </div>

          <div className={styles.errorCard}>
            <span className={styles.errorName}>{entry.name}</span>
            <span className={styles.errorMessage}>{entry.message}</span>
          </div>

          <div className={styles.actions}>
            <button
              type="button"
              className={styles.primary}
              onClick={recovery ? this.continue : () => window.location.reload()}
            >
              {recovery ? "Continue" : "Reload"}
            </button>
            <button type="button" className={styles.secondary} onClick={this.copy}>
              {copyStatus === "copied"
                ? "Copied to clipboard"
                : copyStatus === "failed"
                  ? "Copy failed"
                  : "Copy details"}
            </button>
          </div>

          <details className={styles.details}>
            <summary className={styles.summary}>Technical details</summary>
            <pre className={styles.stack}>{formatCrash(entry)}</pre>
          </details>
        </div>
      </div>
    );
  }
}
