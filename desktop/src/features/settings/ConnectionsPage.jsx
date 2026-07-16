import { useCallback, useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../primitives/Button.jsx";
import ConfirmDelete, { ConfirmDeleteAction } from "../../primitives/ConfirmDelete.jsx";
import Field from "../../primitives/Field.jsx";
import Modal from "../../primitives/Modal.jsx";
import {
  ArrowLeftIcon,
  Checkbox,
  Chip,
  CopyIcon,
  DialogFooter,
  EditIcon,
  Icon,
  IconBtn,
  Mono,
  PauseIcon,
  PlayIcon,
  SearchIcon,
  SettingsHero,
  Tip,
  TrashIcon,
} from "../../primitives/index.js";
import { useNotify } from "../../primitives/Notification.jsx";
import Usage from "./Usage.jsx";
import { PairDeviceModal } from "./fields/devices.jsx";
import { HostPortField, PairingNameField } from "./fields/network.jsx";
import { toUsageDays } from "../../hooks/useUsage.js";
import { copyText } from "../../lib/clipboard.js";
import { profileLabel } from "../../lib/profile-display.js";
import styles from "./ConnectionsPage.module.css";


function since(value) {
  if (!value) return "never";
  const seconds = Math.max(0, Math.floor(Date.now() / 1000 - value));
  if (seconds < 60) return "now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

function usd(value) {
  return `$${Number(value || 0).toFixed(2)}`;
}

function pairingLink(payload) {
  if (!payload?.host || !payload?.port || !payload?.token) return "";
  const query = new URLSearchParams({
    host: payload.host,
    port: String(payload.port),
    name: payload.pairing_name || payload.label || "Alpi",
    token: payload.token,
  });
  return `alpi://device?${query.toString()}`;
}

export default function ConnectionsPage({
  profiles = [],
  activeConnection,
  onBack,
}) {
  const notify = useNotify();
  const connectionArg = activeConnection?.id ? { connectionId: activeConnection.id } : {};
  const [data, setData] = useState(null);
  const [openId, setOpenId] = useState(null);
  const [creating, setCreating] = useState(false);
  const [pairing, setPairing] = useState(null);
  const [editTarget, setEditTarget] = useState(null);
  const [disableTarget, setDisableTarget] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [query, setQuery] = useState("");

  const reload = useCallback(async () => {
    try {
      const next = await invoke("connections_summary", connectionArg);
      setData(next || { connections: [], totals: {} });
    } catch (error) {
      notify({ message: `connections: ${String(error)}`, variant: "error" });
    }
  }, [activeConnection?.id, notify]);

  useEffect(() => { reload(); }, [reload]);

  const rows = data?.connections || [];
  const totals = data?.totals || {};
  const localProfile = activeConnection?.kind === "local"
    ? profiles.find((profile) => profile.name === "default") || null
    : null;
  const defaultProfile = profiles.find((profile) => profile.name === "default") || null;
  const heroTitle = profileLabel("default");
  const heroAccent = defaultProfile?.accent || "var(--accent)";
  const visibleRows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return rows
      .filter((row) => {
        if (!needle) return true;
        return [
          row.id === "host" ? "Local host" : row.label,
          row.role,
          row.status,
          ...(row.devices || []).flatMap((device) => [
            device.name,
            device.client,
            device.app_version,
            device.token_id,
          ]),
        ].filter(Boolean).join(" ").toLowerCase().includes(needle);
      })
      .sort((left, right) => {
        if (left.id === "host") return -1;
        if (right.id === "host") return 1;
        return Number(right.last_seen || 0) - Number(left.last_seen || 0)
          || String(left.label || "").localeCompare(String(right.label || ""));
      });
  }, [query, rows]);
  const heroMeta = (
    <>
      <span>{totals.paired || 0} paired · {totals.connected || 0} connected</span>
      <span className="sep" aria-hidden />
      <span>14-day spend <Mono>{usd(totals.cost_14d)}</Mono></span>
      <span className="sep" aria-hidden />
      <span><Mono>{totals.sessions || 0}</Mono> sessions</span>
    </>
  );

  async function setStatus(row, status) {
    try {
      await invoke("connections_set_status", {
        targetId: row.id,
        status,
        ...connectionArg,
      });
      await reload();
    } catch (error) {
      notify({ message: String(error), variant: "error" });
    }
  }

  async function remove() {
    if (!deleteTarget) return;
    try {
      await invoke("connections_delete", { targetId: deleteTarget.id, ...connectionArg });
      setDeleteTarget(null);
      setOpenId(null);
      await reload();
    } catch (error) {
      notify({ message: String(error), variant: "error" });
    }
  }

  return (
    <main className={styles.page}>
      <SettingsHero
        kind="connections"
        id={heroTitle}
        accent={heroAccent}
        meta={heroMeta}
        actions={(
          <>
            <Button icon={<Icon name="plus" />} onClick={() => setCreating(true)}>New connection</Button>
            <Tip text="Back to settings" side="r">
              <IconBtn onClick={onBack} aria-label="Back to settings"><ArrowLeftIcon /></IconBtn>
            </Tip>
          </>
        )}
      />

      <div className={styles.body}>
        <div className={styles.table}>
          {data && rows.length > 0 && (
            <div className={styles.tableToolbar}>
              <label className={styles.search}>
                <SearchIcon />
                <input
                  type="search"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search connections…"
                  aria-label="Search connections"
                />
              </label>
              <Mono>{visibleRows.length} of {rows.length}</Mono>
            </div>
          )}
          {!data && <div className={styles.empty}>Loading connections…</div>}
          {data && visibleRows.length > 0 && (
            <div className={styles.tableHead} aria-hidden>
              <span>Connection</span>
              <span>Last activity</span>
              <span>Sessions</span>
              <span>14-day spend</span>
            </div>
          )}
          {visibleRows.map((row) => {
            const expanded = openId === row.id;
            const manageable = row.id !== "host";
            return (
              <div
                key={row.id}
                className={`${styles.group} ${expanded ? styles.activeGroup : ""} ${openId && !expanded ? styles.mutedGroup : ""}`}
              >
                <div className={`${styles.row} ${manageable ? styles.manageableRow : ""} ${row.status === "disabled" ? styles.disabledRow : ""}`}>
                  <button
                    type="button"
                    className={styles.rowToggle}
                    aria-expanded={expanded}
                    onClick={() => setOpenId(expanded ? null : row.id)}
                  >
                    <span className={styles.identity}>
                      <strong>{row.id === "host" ? "Local host" : row.label}</strong>
                      {row.id === "host" ? (
                        <Mono>host.sock</Mono>
                      ) : (
                        <span className={styles.identityMeta}>
                          <Mono>{row.devices?.length || 0} devices · {row.role}</Mono>
                          {row.status === "disabled" && <Chip size="sm" state="off">disabled</Chip>}
                        </span>
                      )}
                    </span>
                    <span className={styles.metric}><strong>{since(row.last_seen)}</strong><small>LAST SEEN</small></span>
                    <span className={styles.metric}><strong>{row.sessions || 0}</strong><small>SESSIONS</small></span>
                    <span className={`${styles.metric} ${styles.spend}`}><strong>{usd(row.cost_14d)}</strong><small>14-DAY</small></span>
                  </button>
                  {manageable && (
                    <div className={styles.rowActions}>
                      <IconBtn tip="Edit connection" tipSide="up" onClick={() => setEditTarget(row)}>
                        <EditIcon />
                      </IconBtn>
                      {row.status === "active" ? (
                        <span className={styles.confirmAction}>
                          <IconBtn
                            tip="Disable connection"
                            tipSide="up"
                            onClick={() => setDisableTarget(row)}
                          >
                            <PauseIcon />
                          </IconBtn>
                          <ConfirmDelete
                            open={disableTarget?.id === row.id}
                            title={`Disable ${row.label}?`}
                            consequence={`Its ${row.devices?.length || 0} linked devices will go offline. Sessions and usage remain.`}
                            confirmLabel="Disable connection"
                            onClose={() => setDisableTarget(null)}
                            onConfirm={() => setStatus(row, "disabled")}
                          />
                        </span>
                      ) : (
                        <IconBtn
                          tip="Enable connection"
                          tipSide="up"
                          onClick={() => setStatus(row, "active")}
                        >
                          <PlayIcon />
                        </IconBtn>
                      )}
                      <IconBtn
                        tip="Delete connection"
                        tipSide="up"
                        className={styles.dangerAction}
                        onClick={() => setDeleteTarget(row)}
                      >
                        <TrashIcon />
                      </IconBtn>
                    </div>
                  )}
                </div>
                {expanded && (
                  <ConnectionDetail
                    row={row}
                    connectionArg={connectionArg}
                    localProfile={localProfile}
                    onChanged={reload}
                    onPair={setPairing}
                  />
                )}
              </div>
            );
          })}
          {data && rows.length > 0 && visibleRows.length === 0 && (
            <div className={styles.empty}>No connections match this search.</div>
          )}
        </div>
      </div>

      {creating && (
        <PairDeviceModal
          connectionId={activeConnection?.id || null}
          onClose={() => setCreating(false)}
          onPaired={() => {
            setCreating(false);
            reload();
          }}
        />
      )}
      {pairing && <PairingModal payload={pairing} onClose={() => { setPairing(null); reload(); }} />}
      {editTarget && (
        <EditConnectionModal
          row={editTarget}
          profiles={profiles}
          connectionArg={connectionArg}
          onClose={() => setEditTarget(null)}
          onSaved={() => {
            setEditTarget(null);
            reload();
          }}
        />
      )}
      {deleteTarget && (
        <ConfirmDelete
          open
          mode="typed"
          title={`Delete connection ${deleteTarget.label}?`}
          consequence="Every linked device loses access. Sessions and usage remain attributed to this connection."
          typeToConfirm={deleteTarget.label}
          confirmLabel="Delete connection"
          onClose={() => setDeleteTarget(null)}
          onConfirm={remove}
        />
      )}
    </main>
  );
}


function ConnectionDetail({
  row, connectionArg, localProfile, onChanged, onPair,
}) {
  const notify = useNotify();
  const isHost = row.id === "host";

  async function addDevice() {
    try {
      const payload = await invoke("connections_add_device", {
        targetId: row.id,
        ...connectionArg,
      });
      onPair(payload);
    } catch (error) {
      notify({ message: String(error), variant: "error" });
    }
  }

  async function revoke(device) {
    try {
      await invoke("connections_revoke_device", {
        targetId: row.id,
        deviceId: device.id,
        ...connectionArg,
      });
      onChanged();
    } catch (error) {
      notify({ message: String(error), variant: "error" });
    }
  }

  return (
    <div className={styles.detail}>
      <section className={styles.usageSection}>
        <div className={styles.sectionLabel}>USAGE <span>last 14 days</span></div>
        <Usage days={toUsageDays(row.usage_days)} accent="var(--accent)" />
      </section>

      {isHost && localProfile && (
        <section className={styles.hostSection}>
          <div className={styles.sectionHead}><h2>Pairing</h2></div>
          <PairingNameField />
          <HostPortField profile={localProfile} />
        </section>
      )}

      {!isHost && (
        <section className={styles.devicesSection}>
          <div className={styles.sectionHead}>
            <h2>Devices</h2>
            <Button size="sm" icon={<Icon name="plus" />} onClick={addDevice}>Add device</Button>
          </div>
          <div className={styles.devices}>
            {(row.devices || []).map((device) => (
              <div key={device.id} className={styles.deviceRow}>
                <span><strong>{device.name || "Unnamed device"}</strong><small>{device.client} · {device.app_version || "version unknown"}</small></span>
                <span>
                  <Mono>{since(device.last_seen)}</Mono>
                  <ConfirmDeleteAction
                    label="Revoke"
                    title={`Revoke ${device.name || "device"}?`}
                    consequence="This device loses access immediately. Other devices on the connection keep working."
                    confirmLabel="Revoke device"
                    onConfirm={() => revoke(device)}
                  />
                </span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}


function EditConnectionModal({ row, profiles, connectionArg, onClose, onSaved }) {
  const notify = useNotify();
  const [label, setLabel] = useState(row.label || "");
  const [role, setRole] = useState(row.role || "member");
  const [scope, setScope] = useState(row.profile_scope || []);
  const [allProfiles, setAllProfiles] = useState(!(row.profile_scope || []).length);
  const [busy, setBusy] = useState(false);

  async function save() {
    if (!label.trim() || busy || (role !== "admin" && !allProfiles && !scope.length)) return;
    setBusy(true);
    try {
      await invoke("connections_update", {
        targetId: row.id,
        label: label.trim(),
        role,
        profiles: role === "admin" || allProfiles ? [] : scope,
        ...connectionArg,
      });
      notify({ message: "Connection updated", variant: "success" });
      onSaved();
    } catch (error) {
      notify({ message: String(error), variant: "error" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Edit connection" onClose={onClose} width="var(--modal-md)">
      <div className={styles.modalFields}>
        <label className={styles.manageField}>
          <span className={styles.fieldLabel}>Label</span>
          <Field autoFocus value={label} onChange={(event) => setLabel(event.target.value)} aria-label="Connection label" />
        </label>
        <label className={styles.manageField}>
          <span className={styles.fieldLabel}>Role</span>
          <select value={role} onChange={(event) => setRole(event.target.value)} className={styles.select}>
            <option value="member">Member</option>
            <option value="admin">Admin</option>
          </select>
        </label>
        {role !== "admin" && (
          <div className={styles.manageField}>
            <span className={styles.fieldLabel}>Profiles access</span>
            <div className={styles.profiles}>
              <label>
                <input type="checkbox" checked={allProfiles} onChange={(event) => setAllProfiles(event.target.checked)} />
                <Checkbox on={allProfiles} /> All profiles
              </label>
              {!allProfiles && profiles.map((profile) => (
                <label key={profile.name}>
                  <input type="checkbox" checked={scope.includes(profile.name)} onChange={() => setScope((current) => current.includes(profile.name) ? current.filter((name) => name !== profile.name) : [...current, profile.name])} />
                  <Checkbox on={scope.includes(profile.name)} />@{profileLabel(profile.name)}
                </label>
              ))}
            </div>
          </div>
        )}
      </div>
      <DialogFooter
        onCancel={onClose}
        primaryLabel="Save changes"
        primaryDisabled={!label.trim() || (role !== "admin" && !allProfiles && !scope.length)}
        primaryLoading={busy}
        onPrimary={save}
      />
    </Modal>
  );
}


function PairingModal({ payload, onClose }) {
  const notify = useNotify();
  const [qr, setQr] = useState("");
  const link = useMemo(() => pairingLink(payload), [payload]);

  useEffect(() => {
    let cancelled = false;
    import("qrcode").then(({ default: QRCode }) => QRCode.toString(link, {
      type: "svg", margin: 1, errorCorrectionLevel: "L",
    })).then((svg) => { if (!cancelled) setQr(svg); });
    return () => { cancelled = true; };
  }, [link]);

  async function copy() {
    const ok = await copyText(link);
    notify({ message: ok ? "Pairing link copied" : "Copy failed", variant: ok ? "success" : "error" });
  }

  return (
    <Modal title={`Pair a device with ${payload.label}`} onClose={onClose} width="var(--modal-md)">
      <div className={styles.pairing}>
        <div className={styles.qr} dangerouslySetInnerHTML={{ __html: qr }} />
        <div><Mono>{payload.host}:{payload.port}</Mono><p>Scan from desktop or mobile. This device receives its own credential under the same connection.</p></div>
      </div>
      <div className={styles.link}><Mono>{link}</Mono><Button icon={<CopyIcon />} onClick={copy} title="Copy pairing link" /></div>
      <div className={styles.modalActions}><Button onClick={onClose}>Done</Button></div>
    </Modal>
  );
}
