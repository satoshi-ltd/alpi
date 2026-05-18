// PeerPopover — peers list + drill-in detail in a single popover.
import { useState } from "react";
import Popover from "./Popover.jsx";
import DialogFooter from "./DialogFooter.jsx";
import {
  ActionLink,
  ArrowLeftIcon,
  Diamond,
  Eyebrow,
  IconBtn,
  Mono,
  Pill,
  Tag,
  Tip,
} from "./index.js";
import styles from "./PeerPopover.module.css";

function PeerRow({ peer, onOpen }) {
  return (
    <button type="button" onClick={onOpen} className={styles.row}>
      <Diamond color={peer.accent} />
      <span className={styles.rowId}>{peer.id}</span>
      <Mono className={styles.rowKey}>
        …{(peer.pubkey || "").slice(-7)}
      </Mono>
      <Pill state={peer.online ? "on" : "off"}>
        {peer.online ? "online" : "offline"}
      </Pill>
    </button>
  );
}

function PeerDetail({ peer, onBack, onRemove }) {
  return (
    <div className={styles.detail}>
      <div className={styles.detailHead}>
        <Tip text="Back" side="r">
          <IconBtn aria-label="Back" onClick={onBack}>
            <ArrowLeftIcon />
          </IconBtn>
        </Tip>
        <Diamond color={peer.accent} size={11} />
        <span className={styles.detailHandle}>@{peer.id}</span>
        <span className={styles.detailStatusSlot}>
          <Pill state={peer.online ? "on" : "off"}>
            {peer.online ? "online" : "offline"}
          </Pill>
        </span>
      </div>

      <div className={styles.field}>
        <Eyebrow>Pubkey</Eyebrow>
        <Mono className={styles.pubkey}>{peer.pubkey}</Mono>
      </div>

      {Array.isArray(peer.allow) && peer.allow.length > 0 && (
        <div className={styles.field}>
          <Eyebrow>Allow scopes</Eyebrow>
          <div className={styles.scopes}>
            {peer.allow.map((scope) => (
              <Tag key={scope}>{scope}</Tag>
            ))}
          </div>
        </div>
      )}

      <DialogFooter
        onCancel={onBack}
        cancelLabel="Close"
        primaryLabel="Remove peer"
        destructive
        onPrimary={onRemove}
      />
    </div>
  );
}

export default function PeerPopover({
  open,
  onClose,
  peers = [],
  onRemove,
  onAdd,
  triggerOnAdd,
}) {
  const [detail, setDetail] = useState(null);
  return (
    <Popover open={open} onClose={onClose} width="var(--pop-lg)">
      {detail ? (
        <PeerDetail
          peer={detail}
          onBack={() => setDetail(null)}
          onRemove={() => {
            onRemove?.(detail);
            setDetail(null);
          }}
        />
      ) : (
        <div className={styles.list}>
          <div className={styles.listHead}>
            <Eyebrow>Linked peers · {peers.length}</Eyebrow>
          </div>
          <div className={styles.scroll}>
            {peers.length === 0 && (
              <div className={styles.empty}>No peers linked</div>
            )}
            {peers.map((p) => (
              <PeerRow key={p.pubkey || p.id} peer={p} onOpen={() => setDetail(p)} />
            ))}
          </div>
          {onAdd && (
            <div className={styles.footer}>
              <ActionLink onClick={onAdd}>+ Add peer</ActionLink>
              {triggerOnAdd && (
                <Btn variant="ghost" onClick={triggerOnAdd}>
                  Browse hub
                </Btn>
              )}
            </div>
          )}
        </div>
      )}
    </Popover>
  );
}
