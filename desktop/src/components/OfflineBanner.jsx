import Button from "../primitives/Button.jsx";
import alpiHeadUrl from "../assets/alpi-head.svg?url";
import styles from "./ChatPane.module.css";

export default function OfflineBanner({ connectionName, connectionDetail, onRetry }) {
  return (
    <div className={styles.emptyShell}>
      <div className={styles.emptyContent}>
        <div className={styles.emptyMark}>
          <span
            className={styles.logoImage}
            style={{ "--mask-image": `url(${alpiHeadUrl})` }}
            aria-label="alpi"
          />
        </div>
        <div className={styles.titleGroup}>
          <h1 className={styles.emptyHeading}>
            {connectionName ? `${connectionName} is offline.` : "Connection is offline."}
          </h1>
          {connectionDetail && (
            <p className={styles.emptyModel}>{connectionDetail}</p>
          )}
        </div>
        <Button variant="ghost" size="sm" onClick={onRetry}>
          Retry now
        </Button>
      </div>
    </div>
  );
}
