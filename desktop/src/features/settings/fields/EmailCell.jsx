import { useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { safeUnlisten } from "../../../lib/tauri-listen.js";
import Button from "../../../primitives/Button.jsx";
import Chip from "../../../primitives/Chip.jsx";
import Dot from "../../../primitives/Dot.jsx";
import Eyebrow from "../../../primitives/Eyebrow.jsx";
import Modal from "../../../primitives/Modal.jsx";
import { useNotify } from "../../../primitives/Notification.jsx";
import { Btn } from "../../../primitives/index.js";
import Field from "../../../primitives/Field.jsx";
import { ConfirmDeleteAction } from "../../../primitives/index.js";
import styles from "../Settings.module.css";

function cacheKey(connectionId, profileName) {
  return `${connectionId || "local"}|${profileName}`;
}

const _accountsCache = new Map();

export function _clearEmailAccountsCache() {
  _accountsCache.clear();
}

export function EmailCell({ profile, connectionId = null, onLoadingChange = null }) {
  const key = cacheKey(connectionId, profile.name);
  const [accounts, setAccounts] = useState(() => _accountsCache.get(key) ?? null);
  const [tick, setTick] = useState(0);
  const [editing, setEditing] = useState(null);
  const [adding, setAdding] = useState(false);
  const requestRef = useRef(0);
  const connectionArg = useMemo(
    () => (connectionId ? { connectionId } : {}),
    [connectionId],
  );

  useEffect(() => {
    const requestId = ++requestRef.current;
    setAccounts(_accountsCache.get(key) ?? null);
    setEditing(null);
    onLoadingChange?.(true);
    invoke("email_status", { profile: profile.name, ...connectionArg })
      .then((s) => {
        if (requestRef.current !== requestId) return;
        const next = Array.isArray(s) ? s : [];
        _accountsCache.set(key, next);
        setAccounts(next);
      })
      .catch(() => {
        if (requestRef.current === requestId) setAccounts(_accountsCache.get(key) ?? []);
      })
      .finally(() => {
        if (requestRef.current === requestId) onLoadingChange?.(false);
      });
    return () => {
      requestRef.current += 1;
      onLoadingChange?.(false);
    };
  }, [profile.name, connectionArg, key, tick, onLoadingChange]);

  function refresh() {
    setTick((t) => t + 1);
  }

  return (
    <span className={styles.chipRow}>
      {accounts === null && <span className={styles.muted}>loading…</span>}
      {accounts?.length === 0 && <span className={styles.muted}>none</span>}
      {accounts?.map((a) => (
        <Chip key={a.id} onClick={() => setEditing(a)}>
          {a.address || a.id}
        </Chip>
      ))}
      <Button size="sm" onClick={() => setAdding(true)}>+ Add account</Button>
      {adding && (
        <AddAccountModal
          profile={profile}
          connectionId={connectionId}
          onClose={() => setAdding(false)}
          onSaved={() => { refresh(); setAdding(false); }}
        />
      )}
      {editing && (
        <EmailEditorModal
          profile={profile}
          account={editing}
          connectionId={connectionId}
          onClose={() => setEditing(null)}
          onSaved={() => { refresh(); setEditing(null); }}
        />
      )}
    </span>
  );
}

function FieldLabel({ children, hint }) {
  return (
    <Eyebrow as="label">
      {children}
      {hint && <span className={styles.emailLabelHint}> {hint}</span>}
    </Eyebrow>
  );
}

function ImapFields({ values, set, disabledAddress = false }) {
  return (
    <>
      <div className={styles.field}>
        <FieldLabel>Email address</FieldLabel>
        <Field
          className={`${styles.input} ${styles.inputFull}`}
          value={values.address ?? ""}
          onChange={(e) => set("address", e.target.value)}
          placeholder="you@domain.com"
          spellCheck={false}
          disabled={disabledAddress}
          autoFocus={!disabledAddress}
        />
      </div>
      <div className={styles.field}>
        <FieldLabel hint="· app password if 2FA">Password</FieldLabel>
        <Field
          className={`${styles.input} ${styles.inputFull}`}
          type="password"
          value={values.password ?? ""}
          onChange={(e) => set("password", e.target.value)}
          placeholder={values.passwordSet ? "•••••••• (unchanged)" : "app password if 2FA"}
          spellCheck={false}
        />
      </div>
      <div className={styles.field}>
        <FieldLabel>IMAP host · port</FieldLabel>
        <div className={styles.emailHostPort}>
          <Field
            className={`${styles.input} ${styles.inputFull}`}
            value={values.imap_host ?? ""}
            onChange={(e) => set("imap_host", e.target.value)}
            placeholder="imap.gmail.com"
            spellCheck={false}
          />
          <Field
            className={`${styles.input} ${styles.emailPort}`}
            value={values.imap_port ?? ""}
            onChange={(e) => set("imap_port", e.target.value)}
            placeholder="993"
            spellCheck={false}
          />
        </div>
      </div>
      <div className={styles.field}>
        <FieldLabel>SMTP host · port</FieldLabel>
        <div className={styles.emailHostPort}>
          <Field
            className={`${styles.input} ${styles.inputFull}`}
            value={values.smtp_host ?? ""}
            onChange={(e) => set("smtp_host", e.target.value)}
            placeholder="smtp.gmail.com"
            spellCheck={false}
          />
          <Field
            className={`${styles.input} ${styles.emailPort}`}
            value={values.smtp_port ?? ""}
            onChange={(e) => set("smtp_port", e.target.value)}
            placeholder="587"
            spellCheck={false}
          />
        </div>
      </div>
    </>
  );
}

function GmailFields({ values, set, disabledAddress = false }) {
  return (
    <>
      <div className={styles.field}>
        <FieldLabel>Email address</FieldLabel>
        <Field
          className={`${styles.input} ${styles.inputFull}`}
          value={values.address ?? ""}
          onChange={(e) => set("address", e.target.value)}
          placeholder="you@gmail.com"
          spellCheck={false}
          disabled={disabledAddress}
          autoFocus={!disabledAddress}
        />
      </div>
      <div className={styles.field}>
        <FieldLabel hint="· blank = shared">Client ID</FieldLabel>
        <Field
          className={`${styles.input} ${styles.inputFull}`}
          value={values.client_id ?? ""}
          onChange={(e) => set("client_id", e.target.value)}
          placeholder="OAuth desktop client id"
          spellCheck={false}
        />
      </div>
      <div className={styles.field}>
        <FieldLabel hint="· blank = shared">Client secret</FieldLabel>
        <Field
          className={`${styles.input} ${styles.inputFull}`}
          type="password"
          value={values.client_secret ?? ""}
          onChange={(e) => set("client_secret", e.target.value)}
          placeholder="OAuth client secret"
          spellCheck={false}
        />
      </div>
    </>
  );
}

function AddAccountModal({ profile, connectionId = null, onClose, onSaved }) {
  const notify = useNotify();
  const connectionArg = useMemo(
    () => (connectionId ? { connectionId } : {}),
    [connectionId],
  );
  const [type, setType] = useState("imap");
  const [values, setValues] = useState({});
  const [busy, setBusy] = useState(false);
  const mounted = useRef(true);
  const flowRef = useRef("");

  function set(key, value) {
    setValues((v) => ({ ...v, [key]: value }));
  }
  function field(key) {
    return (values[key] ?? "").trim();
  }

  useEffect(() => {
    mounted.current = true;
    const unlistenPromise = listen("gmail-auth-event", (ev) => {
      if (!mounted.current) return;
      const frame = ev.payload;
      if (frame.flow_id !== flowRef.current) return;
      if ((frame.connection_id ?? null) !== connectionId) return;
      if (frame.event === "authorized") {
        notify({ message: `Gmail authorized as ${frame.email}`, variant: "success" });
        setBusy(false);
        onSaved();
      } else if (frame.event === "error") {
        notify({ message: frame.text || "Gmail auth failed", variant: "error", duration: 5000 });
        setBusy(false);
      }
    });
    return () => {
      mounted.current = false;
      unlistenPromise.then(safeUnlisten).catch(() => {});
    };
  }, [notify, onSaved, connectionId]);

  const canSubmit =
    type === "imap"
      ? !!field("address") && !!field("password") && !!field("imap_host") && !!field("smtp_host") && !busy
      : !!field("address") && !busy;

  async function addImap() {
    setBusy(true);
    try {
      const res = await invoke("email_add", {
        profile: profile.name,
        address: field("address"),
        password: field("password"),
        imapHost: field("imap_host"),
        smtpHost: field("smtp_host"),
        imapPort: field("imap_port") || null,
        smtpPort: field("smtp_port") || null,
        ...connectionArg,
      });
      notify({ message: `${field("address") || res?.id || "Account"} added`, variant: "success" });
      onSaved();
    } catch (e) {
      notify({ message: `add account: ${String(e)}`, variant: "error", duration: 4000 });
      setBusy(false);
    }
  }

  async function authorizeGmail() {
    const flowId = crypto.randomUUID();
    flowRef.current = flowId;
    setBusy(true);
    try {
      await invoke("email_gmail_authorize", {
        profile: profile.name,
        address: field("address"),
        clientId: field("client_id"),
        clientSecret: field("client_secret"),
        flowId,
        ...connectionArg,
      });
    } catch (e) {
      notify({ message: `authorize: ${String(e)}`, variant: "error", duration: 4000 });
      setBusy(false);
    }
  }

  return (
    <Modal title="Add email account" onClose={onClose}>
      <div className={`${styles.field} ${styles.emailTypeToggle}`}>
        <Chip
          state={type === "imap" ? "on" : undefined}
          onClick={busy ? undefined : () => setType("imap")}
        >
          IMAP
        </Chip>
        <Chip
          state={type === "gmail" ? "on" : undefined}
          onClick={busy ? undefined : () => setType("gmail")}
        >
          Gmail
        </Chip>
      </div>
      {type === "imap"
        ? <ImapFields values={values} set={set} />
        : <GmailFields values={values} set={set} />}
      <div className={styles.popoverFooter}>
        <span className={styles.popoverFooterRight}>
          <Btn variant="ghost" onClick={onClose} disabled={busy}>Cancel</Btn>
          {type === "imap" ? (
            <Btn variant="primary" onClick={addImap} disabled={!canSubmit}>
              {busy ? "…" : "Add account"}
            </Btn>
          ) : (
            <Btn variant="primary" onClick={authorizeGmail} disabled={!canSubmit}>
              {busy ? "…" : "Authorize"}
            </Btn>
          )}
        </span>
      </div>
    </Modal>
  );
}

function StatusDot({ status }) {
  const color =
    status === "on"
      ? "var(--c-success)"
      : status === "off" || status === "error"
        ? "var(--c-danger)"
        : "var(--ink-3)";
  return <Dot color={color} className={styles.emailHeaderDot} />;
}

function EmailEditorModal({ profile, account, connectionId = null, onClose, onSaved }) {
  const notify = useNotify();
  const connectionArg = useMemo(
    () => (connectionId ? { connectionId } : {}),
    [connectionId],
  );
  const isGmail = account.type === "gmail";
  const [values, setValues] = useState(null);
  const [probe, setProbe] = useState(null);
  const [testing, setTesting] = useState(false);
  const [busy, setBusy] = useState(false);

  function set(key, value) {
    setValues((v) => ({ ...(v || {}), [key]: value }));
  }

  useEffect(() => {
    let cancelled = false;
    invoke("email_config", { profile: profile.name, id: account.id, ...connectionArg })
      .then((c) => {
        if (cancelled) return;
        const cfg = c ?? {};
        setValues({
          address: cfg.address ?? account.address ?? "",
          imap_host: cfg.imap_host ?? "",
          imap_port: cfg.imap_port != null ? String(cfg.imap_port) : "",
          smtp_host: cfg.smtp_host ?? "",
          smtp_port: cfg.smtp_port != null ? String(cfg.smtp_port) : "",
          password: "",
          passwordSet: !!cfg.password_set,
          client_id: "",
          client_secret: "",
        });
      })
      .catch(() => { if (!cancelled) setValues({ address: account.address ?? "" }); });
    return () => { cancelled = true; };
  }, [profile.name, account.id, account.address, connectionArg]);

  useEffect(() => {
    let cancelled = false;
    if (account.configured) {
      invoke("probe_email", { profile: profile.name, only: [account.id], ...connectionArg })
        .then((r) => {
          if (cancelled) return;
          const hit = Array.isArray(r) ? r.find((p) => p.name === account.id) : null;
          setProbe(hit || { status: "off" });
        })
        .catch(() => { if (!cancelled) setProbe({ status: "off" }); });
    } else {
      setProbe({ status: "off" });
    }
    return () => { cancelled = true; };
  }, [profile.name, account.id, account.configured, connectionArg]);

  async function remove() {
    setBusy(true);
    try {
      await invoke("email_remove", { profile: profile.name, id: account.id, ...connectionArg });
      notify({ message: `${account.address || account.id} removed`, variant: "success" });
      onSaved();
    } catch (e) {
      notify({ message: `remove: ${String(e)}`, variant: "error", duration: 4000 });
      setBusy(false);
    }
  }

  async function test() {
    setTesting(true);
    try {
      const r = await invoke("probe_email", {
        profile: profile.name,
        only: [account.id],
        ...connectionArg,
      });
      const hit = Array.isArray(r) ? r.find((p) => p.name === account.id) : null;
      const result = hit || { status: "off" };
      setProbe(result);
      if (result.status === "on") {
        notify({ message: "Connection OK", variant: "success" });
      } else {
        notify({
          message: result.reason || "Connection failed",
          variant: "error",
          duration: 4000,
        });
      }
    } catch (e) {
      notify({ message: `test: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setTesting(false);
    }
  }

  async function save() {
    setBusy(true);
    try {
      if (isGmail) {
        const id = (values?.client_id ?? "").trim();
        const secret = (values?.client_secret ?? "").trim();
        if (id) {
          await invoke("provider_set_key", {
            profile: profile.name, key: "GMAIL_CLIENT_ID", value: id, ...connectionArg,
          });
        }
        if (secret) {
          await invoke("provider_set_key", {
            profile: profile.name, key: "GMAIL_CLIENT_SECRET", value: secret, ...connectionArg,
          });
        }
      } else {
        await invoke("email_add", {
          profile: profile.name,
          address: (values?.address ?? "").trim(),
          password: (values?.password ?? "").trim(),
          imapHost: (values?.imap_host ?? "").trim(),
          smtpHost: (values?.smtp_host ?? "").trim(),
          imapPort: (values?.imap_port ?? "").trim() || null,
          smtpPort: (values?.smtp_port ?? "").trim() || null,
          ...connectionArg,
        });
      }
      notify({ message: `${account.address || account.id} saved`, variant: "success" });
      onSaved();
    } catch (e) {
      notify({ message: `save: ${String(e)}`, variant: "error", duration: 4000 });
      setBusy(false);
    }
  }

  const title = (
    <span className={styles.emailEditorTitle}>
      {account.address || account.id}
      <StatusDot status={probe?.status} />
    </span>
  );

  return (
    <Modal title={title} onClose={onClose}>
      {values === null ? (
        <div className={styles.muted}>Loading…</div>
      ) : isGmail ? (
        <GmailFields values={values} set={set} disabledAddress />
      ) : (
        <ImapFields values={values} set={set} disabledAddress />
      )}
      <div className={styles.popoverFooter}>
        <ConfirmDeleteAction
          label="Remove account"
          title={`Remove ${account.address || account.id}?`}
          consequence={
            isGmail
              ? "The OAuth token is wiped. You can re-add it later."
              : "The account row and its IMAP password are wiped. You can re-add it later."
          }
          confirmLabel="Remove"
          loading={busy}
          onConfirm={remove}
        />
        <span className={styles.popoverFooterRight}>
          <Btn
            variant="ghost"
            onClick={test}
            disabled={busy || testing || values === null}
          >
            {testing ? "Testing…" : "Test connection"}
          </Btn>
          <Btn variant="ghost" onClick={onClose} disabled={busy}>Cancel</Btn>
          <Btn variant="primary" onClick={save} disabled={busy || values === null}>
            {busy ? "…" : "Save"}
          </Btn>
        </span>
      </div>
    </Modal>
  );
}
