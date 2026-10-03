import { useState } from "react";
import { Button } from "./index.js";
import StepLadder, { ladderSteps } from "./StepLadder.jsx";
import {
  LINK_SOURCES,
  PAIRING_STEPS,
  failedStep,
  pairingFailure,
  pairingFailureKind,
  pairingLinkHost,
  pairingStepLabel,
} from "../../../common/onboarding.mjs";
import styles from "./ConnectElsewhere.module.css";

export default function ConnectElsewhere({ onConnect, autoFocus = false }) {
  const [link, setLink] = useState("");
  const [current, setCurrent] = useState(null);
  const [failure, setFailure] = useState(null);
  const host = pairingLinkHost(link);
  const busy = current !== null && current !== "done" && !failure;

  async function submit(e) {
    e?.preventDefault();
    if (busy) return;
    setFailure(null);
    if (!host) {
      setCurrent("read");
      setFailure(pairingFailure("invalid", null));
      return;
    }
    setCurrent("reach");
    try {
      await onConnect(link.trim());
      setCurrent("done");
    } catch (error) {
      const next = pairingFailure(pairingFailureKind(error), host);
      setFailure(next);
      if (!next.keepLink) setLink("");
    }
  }

  const steps = current
    ? ladderSteps(PAIRING_STEPS, current, failure ? failedStep(failure.kind) : null, (id) => pairingStepLabel(id, host))
    : null;

  return (
    <form className={styles.connect} onSubmit={submit}>
      <input
        className={`field field-mono ${styles.linkInput}`}
        value={link}
        onChange={(e) => setLink(e.target.value)}
        placeholder="alpi://device?url=…"
        aria-label="alpi:// link"
        autoFocus={autoFocus}
      />
      <p className={styles.sources}>{LINK_SOURCES.join(" ")}</p>
      {steps ? <StepLadder steps={steps} /> : null}
      {failure ? (
        <div className={styles.failure} role="alert">
          <strong>{failure.title}</strong>
          <span>{failure.hint}</span>
        </div>
      ) : null}
      <div className={styles.actions}>
        <Button type="submit" variant="primary" disabled={busy || !link.trim()}>
          {failure ? failure.action : "Connect"}
        </Button>
      </div>
    </form>
  );
}
