import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../../primitives/Button.jsx";
import Eyebrow from "../../../primitives/Eyebrow.jsx";
import Chip from "../../../primitives/Chip.jsx";
import Dropdown from "../../../primitives/Dropdown.jsx";
import Textarea from "../../../primitives/Textarea.jsx";
import useAutoPosition from "../../../primitives/useAutoPosition.js";
import { Diamond } from "../../../primitives/index.js";
import Field from "../../../primitives/Field.jsx";
import { useNotify } from "../../../primitives/Notification.jsx";
import { useDismissOnOutside } from "../../../hooks/useDismissOnOutside.js";
import { ConfirmDeleteAction, DialogFooter } from "../../../primitives/index.js";
import { ALLOW_METHODS, isValidEd25519Pubkey } from "../util.js";
import styles from "../Settings.module.css";
import { shortPubkey } from "../../../lib/pubkey.js";

function renderPeerStatusChip(status, reason) {
  if (status === "on") {
    return (
      <Chip size="sm" state="on" tooltip="link.ping ok — mutual pinning, service up">
        online
      </Chip>
    );
  }
  if (status === "unverified") {
    return (
      <Chip
        size="sm"
        state="warn"
        tooltip={
          reason
            ? `handshake failed — peer may not have us pinned, or our pubkey is wrong.\n\n${reason}`
            : "handshake failed — peer may not have us pinned, or our pubkey is wrong."
        }
      >
        unverified
      </Chip>
    );
  }
  if (status === "off") {
    return (
      <Chip
        size="sm"
        state="error"
        tooltip={reason ? `peer service unreachable.\n\n${reason}` : "peer service unreachable."}
      >
        offline
      </Chip>
    );
  }
  return null;
}

export function PeersField({ profile, profiles, onSaved, onRefresh, onLoadingChange = null }) {
  const peers = profile.peers ?? [];
  const [statusById, setStatusById] = useState({});
  const [reasonById, setReasonById] = useState({});
  const [pendingLoading, setPendingLoading] = useState(false);
  const [probeLoading, setProbeLoading] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [selectedPeerId, setSelectedPeerId] = useState(null);
  const [pending, setPending] = useState([]);
  const [pendingTick, setPendingTick] = useState(0);
  const wrapRef = useRef(null);
  const addAnchorRef = useRef(null);
  const detailAnchorRef = useRef(null);
  const notify = useNotify();

  useEffect(() => {
    let cancelled = false;
    setPendingLoading(true);
    invoke("peers_pending_list", { profile: profile.name })
      .then((rows) => !cancelled && setPending(Array.isArray(rows) ? rows : []))
      .catch(() => !cancelled && setPending([]))
      .finally(() => { if (!cancelled) setPendingLoading(false); });
    return () => { cancelled = true; };
  }, [profile.name, pendingTick, peers.length]);

  async function acceptPending(pubkey, suggestedId) {
    let id = (suggestedId || "").trim();
    if (!id) {
      const entered = window.prompt(
        `Pin this peer (pubkey ${shortPubkey(pubkey, 12)}) under what id?`,
        "",
      );
      if (entered === null) return;
      id = (entered || "").trim();
      if (!id) {
        notify({ message: "id required to pin", variant: "error" });
        return;
      }
    }
    try {
      await invoke("peers_pending_accept", {
        profile: profile.name,
        peerId: id,
        pubkey,
      });
      notify({ message: `peer @${id} pinned`, variant: "success" });
      setPendingTick((t) => t + 1);
      await onRefresh?.();
      await onSaved?.();
    } catch (e) {
      notify({ message: `accept: ${String(e)}`, variant: "error", duration: 4000 });
    }
  }

  async function discardPending(pubkey) {
    try {
      await invoke("peers_pending_discard", { profile: profile.name, pubkey });
      setPendingTick((t) => t + 1);
      await onRefresh?.();
    } catch (e) {
      notify({ message: `discard: ${String(e)}`, variant: "error", duration: 3000 });
    }
  }

  useEffect(() => {
    if (peers.length === 0) {
      setStatusById({});
      setReasonById({});
      setProbeLoading(false);
      return undefined;
    }
    let cancelled = false;
    setProbeLoading(true);
    invoke("probe_peers", {
      profile: profile.name,
      ids: peers.map((p) => p.id),
    })
      .then((results) => {
        if (cancelled) return;
        const sMap = {};
        const rMap = {};
        for (const r of results) {
          sMap[r.id] = r.status;
          if (r.reason) rMap[r.id] = r.reason;
        }
        setStatusById(sMap);
        setReasonById(rMap);
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setProbeLoading(false); });
    return () => { cancelled = true; };
  }, [profile.name, peers.length]);

  useEffect(() => {
    onLoadingChange?.(pendingLoading || probeLoading);
  }, [pendingLoading, probeLoading, onLoadingChange]);

  useDismissOnOutside({
    open: addOpen || !!selectedPeerId,
    onClose: () => {
      setAddOpen(false);
      setSelectedPeerId(null);
    },
    wrapRef,
  });

  const onlineCount = Object.values(statusById).filter((s) => s === "on").length;

  async function removePeer(peerId) {
    try {
      await invoke("peer_remove", { profile: profile.name, peerId });
      await onRefresh?.();
      await onSaved?.();
      notify({ message: `peer @${peerId} removed`, variant: "success", duration: 2500 });
    } catch (e) {
      notify({ message: `peer remove: ${String(e)}`, variant: "error", duration: 4000 });
    }
  }

  return (
    <span ref={wrapRef} className={styles.inlineRow}>
      {peers.length === 0 ? (
        <span className={styles.muted}>none</span>
      ) : (
        <span ref={detailAnchorRef} className={styles.popoverAnchor}>
          <Dropdown
            trigger={{
              label:
                peers.length === 1
                  ? `1 peer · ${onlineCount} online`
                  : `${peers.length} peers · ${onlineCount} online`,
            }}
            direction="down"
            align="left"
            width={320}
            variant="field"
          >
            {({ close }) => (
              <>
                {peers.map((p) => {
                  const status = statusById[p.id] ?? "?";
                  const localProfile = profiles?.find((x) => x.name === p.id);
                  const accent = localProfile?.accent || "var(--accent)";
                  return (
                    <Dropdown.Row
                      key={p.id}
                      onClick={() => {
                        close?.();
                        setSelectedPeerId(p.id);
                      }}
                      leading={<Diamond color={accent} />}
                      caption={shortPubkey(p.pubkey)}
                      trailing={renderPeerStatusChip(status, reasonById[p.id])}
                    >
                      @{p.alias || p.id}
                    </Dropdown.Row>
                  );
                })}
              </>
            )}
          </Dropdown>
          {selectedPeerId && (
            <PeerDetailPopover
              peer={peers.find((p) => p.id === selectedPeerId)}
              status={statusById[selectedPeerId] ?? "?"}
              reason={reasonById[selectedPeerId]}
              anchorRef={detailAnchorRef}
              onClose={() => setSelectedPeerId(null)}
              onRemove={async () => {
                await removePeer(selectedPeerId);
                setSelectedPeerId(null);
              }}
            />
          )}
        </span>
      )}
      <span ref={addAnchorRef} className={styles.popoverAnchor}>
        <Button size="sm" onClick={() => setAddOpen((o) => !o)}>
          + Add peer
        </Button>
        {addOpen && (
          <AddPeerPopover
            profile={profile}
            existingIds={peers.map((p) => p.id)}
            anchorRef={addAnchorRef}
            onClose={() => setAddOpen(false)}
            onAdded={async () => { await onRefresh?.(); await onSaved?.(); }}
          />
        )}
      </span>
      {pending.length > 0 && (
        <Dropdown
          trigger={{
            label:
              pending.length === 1
                ? "1 pending invite"
                : `${pending.length} pending invites`,
            variant: "warning",
          }}
          direction="down"
          align="left"
          width={360}
          variant="field"
        >
          {({ close }) =>
            pending.map((p) => (
              <Dropdown.Row
                key={p.pubkey}
                caption={
                  p.local_profile
                    ? `${shortPubkey(p.pubkey)} · first seen ${new Date(
                        (p.first_seen ?? 0) * 1000,
                      ).toLocaleString()}`
                    : `first seen ${new Date(
                        (p.first_seen ?? 0) * 1000,
                      ).toLocaleString()}`
                }
                trailing={
                  <span style={{ display: "inline-flex", gap: "var(--space-2)" }}>
                    <Button
                      size="sm"
                      variant="primary"
                      onClick={(e) => {
                        e.stopPropagation();
                        acceptPending(p.pubkey, p.local_profile);
                        close?.();
                      }}
                    >
                      Accept
                    </Button>
                    <Button
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        discardPending(p.pubkey);
                      }}
                    >
                      Discard
                    </Button>
                  </span>
                }
              >
                {shortPubkey(p.pubkey)}
              </Dropdown.Row>
            ))
          }
        </Dropdown>
      )}
    </span>
  );
}

function PeerDetailPopover({ peer, status, reason, anchorRef, onClose, onRemove }) {
  const popoverRef = useRef(null);
  const [removing, setRemoving] = useState(false);
  const pos = useAutoPosition({
    open: true,
    anchorRef,
    popoverRef,
    direction: "down",
    align: "left",
  });

  if (!peer) return null;

  return (
    <div
      ref={popoverRef}
      className={`${pos.ready ? "anim-pop " : ""}${styles.popover}`}
      style={{
        minWidth: 320,
        maxWidth: pos.maxWidth ?? undefined,
        position: "fixed",
        top: pos.top,
        left: pos.left,
        right: "auto",
        bottom: "auto",
        visibility: pos.ready ? "visible" : "hidden",
      }}
    >
      <div className={styles.field}>
        <Eyebrow as="label">peer</Eyebrow>
        <span className={styles.peerRowName}>@{peer.alias || peer.id}</span>
      </div>
      <div className={styles.field}>
        <Eyebrow as="label">status</Eyebrow>
        <span>{renderPeerStatusChip(status, reason)}</span>
        {reason && status !== "on" && (
          <span className={styles.muted} style={{ marginTop: "var(--space-2)" }}>{reason}</span>
        )}
      </div>
      <div className={styles.field}>
        <Eyebrow as="label">pubkey</Eyebrow>
        <span className={styles.mono}>{peer.pubkey}</span>
      </div>
      {peer.address && (
        <div className={styles.field}>
          <Eyebrow as="label">address</Eyebrow>
          <span className={styles.mono}>{peer.address}</span>
        </div>
      )}
      <div className={styles.field}>
        <Eyebrow as="label">allow</Eyebrow>
        <span className={styles.inlineRow}>
          {(peer.allow ?? []).length === 0 ? (
            <span className={styles.muted}>none</span>
          ) : (
            (peer.allow ?? []).map((m) => (
              <Chip key={m} size="sm" state="on">{m}</Chip>
            ))
          )}
        </span>
      </div>
      <div className={styles.actions}>
        <Button size="sm" onClick={onClose}>Close</Button>
        <ConfirmDeleteAction
          label="Remove peer"
          title={`Remove peer @${peer.id || peer.alias || ""}?`}
          consequence="They lose ALP access from this profile. You can re-add them later."
          confirmLabel="Remove"
          loading={removing}
          onConfirm={async () => {
            setRemoving(true);
            try { await onRemove?.(); }
            finally { setRemoving(false); }
          }}
        />
      </div>
    </div>
  );
}

function AddPeerPopover({ profile, existingIds, anchorRef, onClose, onAdded }) {
  const notify = useNotify();
  const popoverRef = useRef(null);
  const [peerId, setPeerId] = useState("");
  const [pubkey, setPubkey] = useState("");
  const [address, setAddress] = useState("");
  const [alias, setAlias] = useState("");
  const [allow, setAllow] = useState(["link.ping", "link.ask", "link.cancel"]);
  const [saving, setSaving] = useState(false);
  const pos = useAutoPosition({
    open: true,
    anchorRef,
    popoverRef,
    direction: "down",
    align: "left",
  });

  const idTrim = peerId.trim();
  const pubkeyTrim = pubkey.trim();
  const idDuplicate = existingIds.includes(idTrim);
  const idFormatValid = idTrim !== "" && /^[a-z0-9_-]+$/.test(idTrim);
  const pubkeyValid = isValidEd25519Pubkey(pubkeyTrim);
  const valid = idFormatValid && pubkeyTrim !== "" && pubkeyValid && !idDuplicate;

  function toggleAllow(id) {
    setAllow((curr) =>
      curr.includes(id) ? curr.filter((x) => x !== id) : [...curr, id],
    );
  }

  async function save() {
    if (!valid || saving) return;
    setSaving(true);
    try {
      await invoke("peer_add", {
        profile: profile.name,
        peerId: idTrim,
        pubkey: pubkeyTrim,
        address: address.trim() || null,
        alias: alias.trim() || null,
        allow: allow.join(","),
      });
      await onAdded?.();
      notify({ message: `peer @${idTrim} pinned`, variant: "success", duration: 2500 });
      onClose?.();
    } catch (e) {
      notify({ message: `peer add: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      ref={popoverRef}
      className={`${pos.ready ? "anim-pop " : ""}${styles.popover}`}
      style={{
        minWidth: 320,
        maxWidth: pos.maxWidth ?? undefined,
        position: "fixed",
        top: pos.top,
        left: pos.left,
        right: "auto",
        bottom: "auto",
        visibility: pos.ready ? "visible" : "hidden",
      }}
    >
      <div className={styles.field}>
        <Eyebrow as="label">id</Eyebrow>
        <Field
          className={styles.input}
          value={peerId}
          onChange={(e) => setPeerId(e.target.value.toLowerCase())}
          placeholder="peer handle (a-z, 0-9, -, _)"
          spellCheck={false}
          autoFocus
        />
      </div>
      <div className={styles.field}>
        <Eyebrow as="label">pubkey</Eyebrow>
        <Textarea
          className={styles.textarea}
          rows={2}
          value={pubkey}
          onChange={(e) => setPubkey(e.target.value)}
          placeholder="base64 ed25519 pubkey"
          spellCheck={false}
        />
      </div>
      <div className={styles.field}>
        <Eyebrow as="label">address (optional)</Eyebrow>
        <Field
          className={styles.input}
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          placeholder="host:port — leave empty for intra-machine"
          spellCheck={false}
        />
      </div>
      <div className={styles.field}>
        <Eyebrow as="label">alias (optional)</Eyebrow>
        <Field
          className={styles.input}
          value={alias}
          onChange={(e) => setAlias(e.target.value)}
          placeholder="display label"
          spellCheck={false}
        />
      </div>
      <div className={styles.field}>
        <Eyebrow as="label">allow</Eyebrow>
        <span className={styles.inlineRow}>
          {ALLOW_METHODS.map((m) => (
            <Chip
              key={m.id}
              size="sm"
              state={allow.includes(m.id) ? "on" : "off"}
              onClick={() => toggleAllow(m.id)}
              tooltip={m.desc}
            >
              {m.id}
            </Chip>
          ))}
        </span>
      </div>
      {idTrim !== "" && !idFormatValid && (
        <div className={styles.warn}>id can only contain a-z, 0-9, - and _.</div>
      )}
      {idDuplicate && (
        <div className={styles.warn}>@{idTrim} is already pinned.</div>
      )}
      {pubkeyTrim !== "" && !pubkeyValid && (
        <div className={styles.warn}>
          invalid pubkey — expected a base64 Ed25519 key (32 bytes / 44 chars).
        </div>
      )}
      <DialogFooter
        onCancel={onClose}
        primaryLabel="Add peer"
        primaryDisabled={!valid}
        primaryLoading={saving}
        onPrimary={save}
      />
    </div>
  );
}
