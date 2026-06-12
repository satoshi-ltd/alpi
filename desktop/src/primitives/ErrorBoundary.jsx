import React from "react";
import styles from "./ErrorBoundary.module.css";

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("desktop render crash", error, info?.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className={styles.wrap}>
        <div className={styles.title}>Alpi hit an unexpected error</div>
        <div className={styles.message}>
          {String(this.state.error?.message || this.state.error)}
        </div>
        <button
          type="button"
          className={styles.button}
          onClick={() => window.location.reload()}
        >
          Reload
        </button>
      </div>
    );
  }
}
