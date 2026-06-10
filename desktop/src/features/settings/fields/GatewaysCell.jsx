import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { safeUnlisten } from "../../../lib/tauri-listen.js";
import Chip from "../../../primitives/Chip.jsx";
import Eyebrow from "../../../primitives/Eyebrow.jsx";
import Modal from "../../../primitives/Modal.jsx";
import { useNotify } from "../../../primitives/Notification.jsx";
import { Btn } from "../../../primitives/index.js";
import Field from "../../../primitives/Field.jsx";
import { ConfirmDeleteAction } from "../../../primitives/index.js";
import {
  GATEWAY_DESC,
  GATEWAY_FIELDS,
  GATEWAY_LABELS,
} from "../util.js";
import styles from "../Settings.module.css";

export function GatewaysCell({ profile }) {
  const [statuses, setStatuses] = useState([]);
  const [probes, setProbes] = useState(null);
  const [tick, setTick] = useState(0);
  const [editing, setEditing] = useState(null);
  const gatewayServiceOff = profile.subsystems?.gateway === false;

  useEffect(() => {
    let cancelled = false;
    setProbes(null);
    invoke("gateway_status", { profile: profile.name })
      .then((s) => {
        if (cancelled) return;
        setStatuses(s);
        const toProbe = s.filter((g) => g.configured).map((g) => g.name);
        if (toProbe.length === 0) {
          setProbes({});
          return;
        }
        invoke("probe_gateways", { profile: profile.name, only: toProbe })
          .then((r) => {
            if (cancelled) return;
            const map = {};
            for (const p of r) map[p.name] = p;
            setProbes(map);
          })
          .catch(() => { if (!cancelled) setProbes({}); });
      })
      .catch(() => {
        if (!cancelled) {
          setStatuses([]);
          setProbes({});
        }
      });
    return () => { cancelled = true; };
  }, [profile.name, tick]);

  return (
    <span className={styles.gatewayChips}>
      {(statuses.length > 0 ? statuses : [
        { name: "telegram", configured: false },
        { name: "imap", configured: false },
        { name: "gmail", configured: false },
        { name: "matrix", configured: false },
      ]).map((g) => {
        const desc = GATEWAY_DESC[g.name] ?? g.name;
        const probe = probes?.[g.name];
        const probing = g.configured && !probe;
        let status;
        let state;
        if (!g.configured) {
          state = "off";
          status = "not configured";
        } else if (probing) {
          state = undefined;
          status = "probing…";
        } else if (probe?.status === "on") {
          state = "on";
          status = "reachable";
        } else if (probe?.status === "error") {
          state = "error";
          status = probe.reason || "unreachable";
        } else {
          state = "off";
          status = "not configured";
        }
        const tooltip = (
          <>
            <div>{desc}</div>
            <div className={styles.tooltipStatus}>
              {gatewayServiceOff
                ? "gateway service is off — enable it to configure"
                : `${status} · click to edit`}
            </div>
          </>
        );
        return (
          <Chip
            key={g.name}
            state={state}
            activity={probing}
            tooltip={tooltip}
            disabled={gatewayServiceOff}
            onClick={() => setEditing(g.name)}
          >
            {g.name}
          </Chip>
        );
      })}
      {editing && (
        <GatewayEditorModal
          profile={profile}
          gateway={editing}
          onClose={() => setEditing(null)}
          onSaved={() => { setTick((t) => t + 1); setEditing(null); }}
        />
      )}
    </span>
  );
}

function GmailAuthModal({ profile, config, onClose, onSaved }) {
  const notify = useNotify();
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [senders, setSenders] = useState("");
  const [phase, setPhase] = useState("idle");
  const [statusText, setStatusText] = useState("");
  const [busy, setBusy] = useState(false);
  const hydrated = useRef(false);
  const mounted = useRef(true);

  useEffect(() => {
    if (!hydrated.current && config !== null) {
      hydrated.current = true;
      setClientId(config.GMAIL_CLIENT_ID ?? "");
      setSenders(config.GMAIL_ALLOWED_SENDERS ?? "");
    }
  }, [config]);

  const [authUrl, setAuthUrl] = useState("");
  const [pastedUrl, setPastedUrl] = useState("");

  useEffect(() => {
    mounted.current = true;
    const unlistenPromise = listen("gmail-auth-event", (ev) => {
      if (!mounted.current) return;
      const frame = ev.payload;
      if (frame.event === "browser_opened") {
        setPhase("waiting");
        setAuthUrl(frame.auth_url || "");
        setStatusText(
          "Complete the Google consent flow in your browser. If no tab opened, use the link below.",
        );
      } else if (frame.event === "authorized") {
        setPhase("done");
        setAuthUrl("");
        setStatusText(`Authorized as ${frame.email}`);
        setBusy(false);
        notify({ message: `Gmail authorized as ${frame.email}`, variant: "success" });
        onSaved();
      } else if (frame.event === "error") {
        setPhase("error");
        setAuthUrl("");
        setStatusText(frame.text || "authorization failed");
        setBusy(false);
        notify({ message: frame.text || "Gmail auth failed", variant: "error", duration: 5000 });
      }
    });
    return () => {
      mounted.current = false;
      unlistenPromise.then(safeUnlisten).catch(() => {});
    };
  }, [notify, onSaved]);

  async function authorize() {
    const hasStoredId = !!config?.GMAIL_CLIENT_ID;
    const hasStoredSecret = !!config?.GMAIL_CLIENT_SECRET;
    if (!clientId.trim() && !hasStoredId) {
      notify({ message: "Client ID is required", variant: "error" });
      return;
    }
    if (!clientSecret.trim() && !hasStoredSecret) {
      notify({ message: "Client Secret is required", variant: "error" });
      return;
    }
    setBusy(true);
    setPhase("waiting");
    setStatusText("Opening browser…");
    try {
      await invoke("gateway_gmail_authorize", {
        profile: profile.name,
        clientId: clientId.trim(),
        clientSecret: clientSecret.trim(),
        allowedSenders: senders.trim(),
      });
    } catch (e) {
      setPhase("error");
      setStatusText(String(e));
      setBusy(false);
    }
  }

  async function submitPastedCallback() {
    const url = pastedUrl.trim();
    if (!url) return;
    setBusy(true);
    setStatusText("Exchanging code with Google…");
    try {
      await invoke("gateway_gmail_paste", { pastedUrl: url });
    } catch (e) {
      setPhase("error");
      setStatusText(String(e));
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await invoke("gateway_remove", { profile: profile.name, name: "gmail" });
      notify({ message: "Gmail gateway removed", variant: "success" });
      onSaved();
    } catch (e) {
      notify({ message: `remove: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Gmail gateway" onClose={onClose}>
      <div className={styles.field}>
        <Eyebrow as="label">Client ID</Eyebrow>
        <Field
          className={`${styles.input} ${styles.inputFull}`}
          type="text"
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          placeholder="OAuth Desktop client ID from Google Cloud"
          spellCheck={false}
          disabled={busy}
        />
      </div>
      <div className={styles.field}>
        <Eyebrow as="label">Client Secret</Eyebrow>
        <Field
          className={`${styles.input} ${styles.inputFull}`}
          type="password"
          value={clientSecret}
          onChange={(e) => setClientSecret(e.target.value)}
          placeholder={
            config?.GMAIL_CLIENT_SECRET
              ? `current: ${config.GMAIL_CLIENT_SECRET} (paste to replace)`
              : "OAuth client secret"
          }
          spellCheck={false}
          disabled={busy}
        />
      </div>
      <div className={styles.field}>
        <Eyebrow as="label">Allowed senders</Eyebrow>
        <Field
          className={`${styles.input} ${styles.inputFull}`}
          type="text"
          value={senders}
          onChange={(e) => setSenders(e.target.value)}
          placeholder="comma-separated emails (empty = no inbound)"
          spellCheck={false}
          disabled={busy}
        />
      </div>
      {statusText && (
        <div
          className={`${styles.muted} ${styles.gmailAuthStatus} ${
            phase === "error"
              ? styles.gmailAuthStatusError
              : phase === "done"
                ? styles.gmailAuthStatusDone
                : ""
          }`}
        >
          {statusText}
        </div>
      )}
      {phase === "waiting" && authUrl && (
        <div className={`${styles.muted} ${styles.gmailAuthUrl}`}>
          <a href={authUrl} target="_blank" rel="noreferrer">
            {authUrl}
          </a>
        </div>
      )}
      {phase === "waiting" && (
        <details className={styles.gmailPasteFallback}>
          <summary className={styles.gmailPasteSummary}>
            Browser on a different machine? Paste the callback URL
          </summary>
          <p className={`${styles.muted} ${styles.gmailPasteHint}`}>
            After authorizing in your browser, Google redirects to a
            <code> http://127.0.0.1:…/?code=… </code> URL that fails to
            load. Copy that full URL from the address bar and paste it
            here.
          </p>
          <textarea
            className={styles.gmailPasteInput}
            placeholder="http://127.0.0.1:55989/?code=…&state=…"
            value={pastedUrl}
            onChange={(e) => setPastedUrl(e.target.value)}
            rows={3}
            spellCheck={false}
            disabled={busy && phase !== "waiting"}
          />
          <Btn
            variant="primary"
            onClick={submitPastedCallback}
            disabled={!pastedUrl.trim() || (busy && statusText.startsWith("Exchanging"))}
          >
            Use pasted URL
          </Btn>
        </details>
      )}
      <div className={styles.popoverFooter}>
        {config?.GMAIL_CLIENT_ID && !busy && (
          <ConfirmDeleteAction
            label="Remove"
            title="Remove Gmail gateway?"
            consequence="The OAuth credentials are wiped. You can re-authorize later."
            confirmLabel="Remove"
            onConfirm={remove}
          />
        )}
        <span className={styles.popoverFooterRight}>
          <Btn variant="ghost" onClick={onClose}>
            {busy ? "Cancel" : "Close"}
          </Btn>
          {!busy && (
            <Btn variant="primary" onClick={authorize}>
              {config?.GMAIL_CLIENT_ID ? "Re-authorize" : "Authorize"}
            </Btn>
          )}
        </span>
      </div>
    </Modal>
  );
}

function GatewayEditorModal({ profile, gateway, onClose, onSaved }) {
  const notify = useNotify();
  const [config, setConfig] = useState(null);
  const [values, setValues] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    invoke("gateway_config", { profile: profile.name, name: gateway })
      .then((c) => {
        if (cancelled) return;
        setConfig(c);
        const fields = GATEWAY_FIELDS[gateway] ?? [];
        const initial = {};
        for (const f of fields) {
          if (!f.secret) initial[f.env] = c[f.env] ?? "";
          else initial[f.env] = "";
        }
        setValues(initial);
      })
      .catch(() => { if (!cancelled) setConfig({}); });
    return () => { cancelled = true; };
  }, [profile.name, gateway]);

  if (gateway === "gmail") {
    return (
      <GmailAuthModal
        profile={profile}
        config={config}
        onClose={onClose}
        onSaved={onSaved}
      />
    );
  }

  const fields = GATEWAY_FIELDS[gateway] ?? [];
  const isConfigured = !!config && Object.keys(config).length > 0;

  async function save() {
    const missing = fields.filter((f) => {
      if (!f.required) return false;
      const next = (values[f.env] ?? "").trim();
      if (next) return false;
      if (f.secret && config?.[f.env]) return false;
      return true;
    });
    if (missing.length > 0) {
      notify({
        message: `Missing required: ${missing.map((f) => f.label).join(", ")}`,
        variant: "error",
        duration: 4000,
      });
      return;
    }
    setBusy(true);
    try {
      for (const f of fields) {
        const next = (values[f.env] ?? "").trim();
        if (f.secret) {
          if (next) {
            await invoke("provider_set_key", {
              profile: profile.name,
              key: f.env,
              value: next,
            });
          }
        } else {
          if (next === "") {
            const had = config?.[f.env];
            if (had) {
              await invoke("provider_unset_key", { profile: profile.name, key: f.env });
            }
          } else if (next !== (config?.[f.env] ?? "")) {
            await invoke("provider_set_key", {
              profile: profile.name,
              key: f.env,
              value: next,
            });
          }
        }
      }
      // The daemon hot-reloads the gateway poller on its next config rescan (≤5s) — no restart, no dropped connections.
      notify({
        message: `${gateway} saved · applying`,
        variant: "success",
        duration: 3000,
      });
      onSaved();
    } catch (e) {
      notify({ message: `save: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await invoke("gateway_remove", { profile: profile.name, name: gateway });
      notify({ message: `${gateway} gateway removed`, variant: "success" });
      onSaved();
    } catch (e) {
      notify({ message: `remove: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title={`${GATEWAY_LABELS[gateway] ?? gateway} gateway`}
      onClose={onClose}
    >
      {fields.map((f) => {
        const preview = f.secret ? config?.[f.env] : null;
        return (
          <div key={f.env} className={styles.field}>
            <Eyebrow as="label">
              {f.label}
              {f.required && <span aria-hidden="true"> *</span>}
            </Eyebrow>
            <Field
              className={`${styles.input} ${styles.inputFull}`}
              type={f.secret ? "password" : "text"}
              value={values[f.env] ?? ""}
              onChange={(e) =>
                setValues((v) => ({ ...v, [f.env]: e.target.value }))
              }
              placeholder={
                f.secret && preview
                  ? `current: ${preview} (paste to replace)`
                  : f.hint
              }
              spellCheck={false}
            />
          </div>
        );
      })}
      <div className={styles.popoverFooter}>
        {isConfigured && (
          <ConfirmDeleteAction
            label="Remove"
            title={`Remove ${GATEWAY_LABELS[gateway] ?? gateway} gateway?`}
            consequence="The gateway credentials are wiped. You can re-add them later."
            confirmLabel="Remove"
            loading={busy}
            onConfirm={remove}
          />
        )}
        <span className={styles.popoverFooterRight}>
          <Btn variant="ghost" onClick={onClose} disabled={busy}>Cancel</Btn>
          <Btn variant="primary" onClick={save} disabled={busy}>
            {busy ? "…" : "Save"}
          </Btn>
        </span>
      </div>
    </Modal>
  );
}
