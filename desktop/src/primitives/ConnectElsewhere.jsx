import { useEffect, useId, useRef, useState } from "react";
import { Button, Mono } from "./index.js";
import StepLadder, { ladderSteps } from "./StepLadder.jsx";
import {
  LINK_SOURCE_ROWS,
  PAIRING_STEPS,
  failedStep,
  pairingFailure,
  pairingFailureKind,
  pairingLinkHost,
  pairingStepLabel,
} from "../../../common/onboarding.mjs";
import styles from "./ConnectElsewhere.module.css";

export default function ConnectElsewhere({ onConnect, onBack = null, autoFocus = false, initialLink = "", onLinkChange = null }) {
  const fieldId = useId();
  const fieldRef = useRef(null);
  const [link, setLinkState] = useState(initialLink);
  const setLink = (value) => {
    setLinkState(value);
    onLinkChange?.(value);
  };
  useEffect(() => {
    if (autoFocus) fieldRef.current?.focus({ preventScroll: true });
  }, [autoFocus]);
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
      <label className={styles.label} htmlFor={fieldId}>alpi:// link</label>
      <input
        id={fieldId}
        ref={fieldRef}
        className={`field field-mono ${styles.linkInput}`}
        value={link}
        onChange={(e) => setLink(e.target.value)}
        placeholder="alpi://device?url=…"
      />
      <div className={styles.middle}>
        {steps ? (
          <StepLadder steps={steps} />
        ) : (
          <ul className={styles.sources}>
            {LINK_SOURCE_ROWS.map(({ label, path }) => (
              <li key={label} className={styles.source}>
                <span className={styles.sourceLabel}>{label}</span>
                <Mono className={styles.sourcePath}>{path}</Mono>
              </li>
            ))}
          </ul>
        )}
      </div>
      {failure ? (
        <div className={styles.failure} role="alert">
          <strong>{failure.title}</strong>
          <span>{failure.hint}</span>
        </div>
      ) : null}
      <div className={styles.actions}>
        <Button type="submit" variant="primary" size="lg" className={styles.primary} disabled={busy || !link.trim()}>
          {failure ? failure.action : "Connect"}
        </Button>
        {onBack ? <Button variant="ghost" size="lg" onClick={onBack}>Back</Button> : null}
      </div>
    </form>
  );
}
