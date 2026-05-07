import Button from "../primitives/Button.jsx";
import alpiHeadUrl from "../assets/alpi-head.svg?url";
import chatStyles from "./ChatPane.module.css";
import styles from "./OfflineBanner.module.css";

export default function OfflineBanner({ connectionName, connectionDetail, onRetry }) {
  return (
    <div className={chatStyles.emptyShell}>
      <div className={chatStyles.emptyContent}>
        <div className={chatStyles.emptyMark}>
          <img className={chatStyles.logoImage} src={alpiHeadUrl} alt="alpi" />
        </div>
        <div className={styles.titleGroup}>
          <h1 className={chatStyles.emptyHeading}>
            {connectionName ? `${connectionName} is offline.` : "Connection is offline."}
          </h1>
          {connectionDetail && (
            <p className={chatStyles.emptyModel}>{connectionDetail}</p>
          )}
        </div>
        <p className={`${chatStyles.emptyHint} ${styles.hint}`}>
          The daemon is unreachable. Retrying automatically.
        </p>
        <Button variant="ghost" size="sm" onClick={onRetry}>
          Retry now
        </Button>
      </div>
    </div>
  );
}
