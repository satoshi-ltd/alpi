import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../../primitives/Button.jsx";
import Chip from "../../../primitives/Chip.jsx";
import Dropdown from "../../../primitives/Dropdown.jsx";
import Textarea from "../../../primitives/Textarea.jsx";
import useAutoPosition from "../../../primitives/useAutoPosition.js";
import { AccentDot } from "../../../primitives/NavRow.jsx";
import { useNotify } from "../../../primitives/Notification.jsx";
import { ConfirmButton } from "../primitives.jsx";
import {
  ALLOW_METHODS,
  formatTcpLabel,
  isValidEd25519Pubkey,
} from "../util.js";
import styles from "../../Settings.module.css";

export function TcpPortField({ profile, onSaved }) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const notify = useNotify();
  const [host, setHost] = useState(profile.tcp_host || "127.0.0.1");
  const [port, setPort] = useState(
    profile.tcp_port ? String(profile.tcp_port) : "",
  );
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setHost(profile.tcp_host || "127.0.0.1");
    setPort(profile.tcp_port ? String(profile.tcp_port) : "");
  }, [profile.tcp_host, profile.tcp_port]);

  useEffect(() => {
    if (!open) return;
    function onClick(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const portTrim = port.trim();
  const portValid = portTrim === "" || /^[0-9]+$/.test(portTrim);
  const portNum = portTrim === "" ? 0 : Number(portTrim);
  const portInRange = portTrim === "" || (portNum >= 1 && portNum <= 65535);
  const dirty =
    host.trim() !== (profile.tcp_host || "127.0.0.1") ||
    portTrim !== (profile.tcp_port ? String(profile.tcp_port) : "");

  const [portFree, setPortFree] = useState(null);
  useEffect(() => {
    if (!open || !portInRange || portTrim === "") {
      setPortFree(null);
      return;
    }
    if (portNum === profile.tcp_port) {
      setPortFree(true);
      return;
    }
    let cancelled = false;
    const id = setTimeout(() => {
      invoke("port_available", {
        host: host.trim() || "127.0.0.1",
        port: portNum,
      })
        .then((ok) => { if (!cancelled) setPortFree(ok); })
        .catch(() => { if (!cancelled) setPortFree(null); });
    }, 350);
    return () => { cancelled = true; clearTimeout(id); };
  }, [open, portTrim, portNum, host, portInRange, profile.tcp_port]);

  async function save() {
    if (!portValid || !portInRange || saving) return;
    if (portTrim !== "" && portFree === false) return;
    setSaving(true);
    try {
      if (portTrim === "") {
        await invoke("unset_config_field", { profile: profile.name, key: "alp.tcp_port" });
        await invoke("unset_config_field", { profile: profile.name, key: "alp.tcp_host" });
      } else {
        await invoke("set_config_field", {
          profile: profile.name,
          key: "alp.tcp_host",
          value: host.trim() || "127.0.0.1",
        });
        await invoke("set_config_field", {
          profile: profile.name,
          key: "alp.tcp_port",
          value: portTrim,
        });
      }
      invoke("daemon_restart").catch(() => {});
      await onSaved?.();
      notify({
        message: portTrim
          ? `TCP listener ${host.trim()}:${portTrim} · daemon restarting`
          : "TCP listener disabled · daemon restarting",
        variant: "success",
        duration: 3000,
      });
      setOpen(false);
    } catch (e) {
      notify({ message: `tcp: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setSaving(false);
    }
  }

  return (
    <span ref={wrapRef} className={styles.popoverAnchor}>
      <Chip
        state={profile.tcp_port ? "on" : "off"}
        onClick={() => setOpen((o) => !o)}
        tooltip={
          <>
            <div>ALP TCP listener</div>
            <div className={styles.tooltipStatus}>
              {profile.tcp_port
                ? `${profile.tcp_host || "127.0.0.1"}:${profile.tcp_port} · click to edit`
                : "disabled · click to enable"}
            </div>
          </>
        }
      >
        {profile.tcp_port
          ? formatTcpLabel(profile.tcp_host, profile.tcp_port)
          : "tcp off"}
      </Chip>
      {open && (
        <div className={styles.popover}>
          <div className={styles.field}>
            <label className={styles.label}>host</label>
            <input
              className={styles.input}
              value={host}
              onChange={(e) => setHost(e.target.value)}
              placeholder="127.0.0.1"
              spellCheck={false}
            />
          </div>
          <div className={styles.field}>
            <label className={styles.label}>port</label>
            <input
              className={styles.input}
              value={port}
              onChange={(e) => setPort(e.target.value)}
              placeholder="empty to disable"
              spellCheck={false}
            />
          </div>
          {host.trim() === "0.0.0.0" && (
            <div className={styles.warn}>
              0.0.0.0 exposes the port to all interfaces. Use only behind a VPN.
            </div>
          )}
          {!portInRange && (
            <div className={styles.warn}>Port must be 1-65535.</div>
          )}
          {portInRange && portTrim !== "" && portFree === false && (
            <div className={styles.warn}>
              Port {portTrim} is in use on {host.trim() || "127.0.0.1"}.
            </div>
          )}
          <div className={styles.actions}>
            <Button
              size="sm"
              onClick={save}
              disabled={
                !dirty ||
                !portInRange ||
                (portTrim !== "" && portFree === false)
              }
              loading={saving}
              variant="primary"
            >
              Save
            </Button>
          </div>
        </div>
      )}
    </span>
  );
}

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

export function PeersField({ profile, profiles, onSaved }) {
  const peers = profile.peers ?? [];
  const [statusById, setStatusById] = useState({});
  const [reasonById, setReasonById] = useState({});
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
    invoke("peers_pending_list", { profile: profile.name })
      .then((rows) => !cancelled && setPending(Array.isArray(rows) ? rows : []))
      .catch(() => !cancelled && setPending([]));
    return () => { cancelled = true; };
  }, [profile.name, pendingTick, peers.length]);

  async function acceptPending(pubkey, suggestedId) {
    let id = (suggestedId || "").trim();
    if (!id) {
      const entered = window.prompt(
        `Pin this peer (pubkey ${pubkey.slice(0, 12)}…) under what id?`,
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
      await onSaved?.();
    } catch (e) {
      notify({ message: `accept: ${String(e)}`, variant: "error", duration: 4000 });
    }
  }

  async function discardPending(pubkey) {
    try {
      await invoke("peers_pending_discard", { profile: profile.name, pubkey });
      setPendingTick((t) => t + 1);
    } catch (e) {
      notify({ message: `discard: ${String(e)}`, variant: "error", duration: 3000 });
    }
  }

  useEffect(() => {
    if (peers.length === 0) return;
    let cancelled = false;
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
      .catch(() => {});
    return () => { cancelled = true; };
  }, [profile.name, peers.length]);

  useEffect(() => {
    if (!addOpen && !selectedPeerId) return;
    function onClick(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setAddOpen(false);
        setSelectedPeerId(null);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [addOpen, selectedPeerId]);

  const onlineCount = Object.values(statusById).filter((s) => s === "on").length;

  async function removePeer(peerId) {
    try {
      await invoke("peer_remove", { profile: profile.name, peerId });
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
            variant="outlined"
          >
            {({ close }) => (
              <>
                {peers.map((p) => {
                  const status = statusById[p.id] ?? "?";
                  const localProfile = profiles?.find((x) => x.name === p.id);
                  const accent = localProfile?.accent || "var(--color-accent)";
                  return (
                    <Dropdown.Row
                      key={p.id}
                      onClick={() => {
                        close?.();
                        setSelectedPeerId(p.id);
                      }}
                      leading={<AccentDot color={accent} />}
                      caption={(p.pubkey || "").slice(0, 16) + "…"}
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
            onAdded={onSaved}
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
          variant="outlined"
        >
          {({ close }) =>
            pending.map((p) => (
              <Dropdown.Row
                key={p.pubkey}
                caption={
                  p.local_profile
                    ? `${(p.pubkey || "").slice(0, 16)}… · first seen ${new Date(
                        (p.first_seen ?? 0) * 1000,
                      ).toLocaleString()}`
                    : `first seen ${new Date(
                        (p.first_seen ?? 0) * 1000,
                      ).toLocaleString()}`
                }
                trailing={
                  <span style={{ display: "inline-flex", gap: 6 }}>
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
                {(p.pubkey || "").slice(0, 16)}…
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
      className={styles.popover}
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
        <label className={styles.label}>peer</label>
        <span className={styles.peerRowName}>@{peer.alias || peer.id}</span>
      </div>
      <div className={styles.field}>
        <label className={styles.label}>status</label>
        <span>{renderPeerStatusChip(status, reason)}</span>
        {reason && status !== "on" && (
          <span className={styles.muted} style={{ marginTop: "var(--space-2)" }}>{reason}</span>
        )}
      </div>
      <div className={styles.field}>
        <label className={styles.label}>pubkey</label>
        <span className={styles.mono}>{peer.pubkey}</span>
      </div>
      {peer.address && (
        <div className={styles.field}>
          <label className={styles.label}>address</label>
          <span className={styles.mono}>{peer.address}</span>
        </div>
      )}
      <div className={styles.field}>
        <label className={styles.label}>allow</label>
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
        <ConfirmButton
          size="sm"
          label="Remove peer"
          confirmLabel="Confirm remove"
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
      className={styles.popover}
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
        <label className={styles.label}>id</label>
        <input
          className={styles.input}
          value={peerId}
          onChange={(e) => setPeerId(e.target.value.toLowerCase())}
          placeholder="peer handle (a-z, 0-9, -, _)"
          spellCheck={false}
          autoFocus
        />
      </div>
      <div className={styles.field}>
        <label className={styles.label}>pubkey</label>
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
        <label className={styles.label}>address (optional)</label>
        <input
          className={styles.input}
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          placeholder="host:port — leave empty for intra-machine"
          spellCheck={false}
        />
      </div>
      <div className={styles.field}>
        <label className={styles.label}>alias (optional)</label>
        <input
          className={styles.input}
          value={alias}
          onChange={(e) => setAlias(e.target.value)}
          placeholder="display label"
          spellCheck={false}
        />
      </div>
      <div className={styles.field}>
        <label className={styles.label}>allow</label>
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
      <div className={styles.actions}>
        <Button
          size="sm"
          variant="primary"
          onClick={save}
          disabled={!valid}
          loading={saving}
        >
          Add peer
        </Button>
      </div>
    </div>
  );
}

export function WorkgroupsField({ profile, profiles, onSelectWorkgroup }) {
  const [groups, setGroups] = useState([]);
  useEffect(() => {
    invoke("workgroups", { profile: profile.name })
      .then(setGroups)
      .catch(() => setGroups([]));
  }, [profile.name]);

  if (groups.length === 0) {
    return <span className={styles.muted}>none</span>;
  }

  const hubCount = groups.filter((g) => g.is_hub).length;
  const countLabel =
    groups.length === 1 ? "1 workgroup" : `${groups.length} workgroups`;
  const hubLabel =
    hubCount === 0
      ? ""
      : ` · ${hubCount} ${hubCount === 1 ? "hub" : "hubs"}`;

  return (
    <Dropdown
      trigger={{ label: `${countLabel}${hubLabel}` }}
      direction="down"
      align="left"
      width={320}
      variant="outlined"
    >
      {({ close }) => (
        <>
          {groups.map((g) => {
            const hubAccent =
              profiles?.find((p) => p.name === (g.hub_id ?? profile.name))
                ?.accent || "var(--color-accent)";
            return (
              <Dropdown.Row
                key={g.id}
                onClick={() => {
                  onSelectWorkgroup?.(g.id);
                  close?.();
                }}
                caption={`${g.members} ${g.members === 1 ? "member" : "members"}`}
                trailing={
                  g.is_hub ? (
                    <Chip size="sm" accent={hubAccent}>hub</Chip>
                  ) : (
                    <Chip size="sm">member</Chip>
                  )
                }
              >
                #{g.name || g.id}
              </Dropdown.Row>
            );
          })}
        </>
      )}
    </Dropdown>
  );
}

export function BudgetEditor({ current, onSave }) {
  const [open, setOpen] = useState(false);
  const anchorRef = useRef(null);
  const popoverRef = useRef(null);
  const wrapRef = useRef(null);
  const [value, setValue] = useState(current != null ? String(current) : "");
  const [saving, setSaving] = useState(false);
  const pos = useAutoPosition({
    open,
    anchorRef,
    popoverRef,
    direction: "down",
    align: "left",
  });

  useEffect(() => {
    if (open) setValue(current != null ? String(current) : "");
  }, [open, current]);

  useEffect(() => {
    if (!open) return;
    function onClick(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const trimmed = value.trim();
  const parsed = trimmed === "" ? null : Number(trimmed);
  const valid = trimmed === "" || (Number.isFinite(parsed) && parsed > 0);
  const dirty = valid && (parsed ?? null) !== (current ?? null);

  async function save() {
    if (!valid || !dirty || saving) return;
    setSaving(true);
    try {
      await onSave?.(parsed);
      setOpen(false);
    } catch {
    } finally {
      setSaving(false);
    }
  }

  return (
    <span ref={wrapRef} className={styles.popoverAnchor}>
      <span ref={anchorRef}>
        <Button size="sm" onClick={() => setOpen((o) => !o)}>
          {current != null ? "Edit" : "Set cap"}
        </Button>
      </span>
      {open && (
        <div
          ref={popoverRef}
          className={styles.popover}
          style={{
            minWidth: 260,
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
            <label className={styles.label}>USD lifetime cap</label>
            <input
              className={styles.input}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="empty = unlimited"
              spellCheck={false}
              autoFocus
            />
          </div>
          {!valid && <div className={styles.warn}>must be a positive number</div>}
          <div className={styles.actions}>
            <Button
              size="sm"
              variant="primary"
              onClick={save}
              disabled={!valid || !dirty}
              loading={saving}
            >
              Save
            </Button>
          </div>
        </div>
      )}
    </span>
  );
}
