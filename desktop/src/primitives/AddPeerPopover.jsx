import { useState } from "react";
import Popover from "./Popover.jsx";
import { ActionLink, Btn, Eyebrow, Field, Mono } from "./index.js";
import styles from "./AddPeerPopover.module.css";

export default function AddPeerPopover({ open, onClose, onPair }) {
  const [payload, setPayload] = useState("");
  return (
    <Popover open={open} onClose={onClose} width="var(--pop-lg)">
      <div className={styles.body}>
        <Eyebrow>Add peer</Eyebrow>
        <Mono className={styles.help}>
          Paste an <code className="mono">alpi://link</code> invite or scan
          their QR from the host.
        </Mono>
        <Field
          multiline
          mono
          rows={4}
          value={payload}
          onChange={(e) => setPayload(e.target.value)}
          placeholder="alpi://link?v=2&pubkey=…&host=…"
        />
        <div className="row between">
          <ActionLink onClick={onClose}>Cancel</ActionLink>
          <Btn
            variant="primary"
            disabled={!payload.trim()}
            onClick={() => {
              const text = payload.trim();
              if (!text) return;
              onPair?.(text);
              setPayload("");
              onClose?.();
            }}
          >
            Pair
          </Btn>
        </div>
      </div>
    </Popover>
  );
}
