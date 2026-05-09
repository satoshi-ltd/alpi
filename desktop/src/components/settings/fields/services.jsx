import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import Button from "../../../primitives/Button.jsx";
import Chip from "../../../primitives/Chip.jsx";
import Modal from "../../../primitives/Modal.jsx";
import { useNotify } from "../../../primitives/Notification.jsx";
import { Section, Row, ConfirmButton } from "../primitives.jsx";
import {
  GATEWAY_DESC,
  GATEWAY_FIELDS,
  GATEWAY_LABELS,
  SUBSYSTEMS,
  SUBSYSTEM_DESC,
  scheduleSummary,
} from "../util.js";
import styles from "../../Settings.module.css";

export function SubsystemsCell({ profile, onSaved }) {
  const notify = useNotify();
  const [busy, setBusy] = useState(null);
  const subs = profile.subsystems ?? {
    gateway: true,
    schedule: true,
    alp: true,
    workgroups: true,
  };
  async function toggle(key) {
    if (busy) return;
    const next = !subs[key];
    setBusy(key);
    try {
      await invoke("set_config_field", {
        profile: profile.name,
        key: `service.${key}`,
        value: String(next),
      });
      if (profile.running) {
        invoke("daemon_restart").catch(() => {});
      }
      await onSaved?.();
      notify({
        message: profile.running
          ? `${key} ${next ? "enabled" : "disabled"} · daemon restarting`
          : `${key} ${next ? "enabled" : "disabled"}`,
        variant: "success",
        duration: profile.running ? 3000 : 2400,
      });
    } catch (e) {
      notify({ message: `${key}: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setBusy(null);
    }
  }
  return (
    <span className={styles.gatewayChips}>
      {SUBSYSTEMS.map((k) => {
        const enabled = subs[k];
        const state = !profile.running ? "off" : enabled ? "on" : "error";
        const desc = SUBSYSTEM_DESC[k];
        const status = !profile.running
          ? "daemon stopped"
          : enabled
            ? "running · click to disable"
            : "disabled · click to enable";
        const tooltip = (
          <>
            <div>{desc}</div>
            <div className={styles.tooltipStatus}>{status}</div>
          </>
        );
        return (
          <Chip
            key={k}
            state={state}
            tooltip={tooltip}
            onClick={busy ? undefined : () => toggle(k)}
          >
            {k}
          </Chip>
        );
      })}
    </span>
  );
}

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

  useEffect(() => {
    mounted.current = true;
    const unlistenPromise = listen("gmail-auth-event", (ev) => {
      if (!mounted.current) return;
      const frame = ev.payload;
      if (frame.event === "browser_opened") {
        setPhase("waiting");
        setStatusText("Browser opened — complete the Google consent flow…");
      } else if (frame.event === "authorized") {
        setPhase("done");
        setStatusText(`Authorized as ${frame.email}`);
        setBusy(false);
        notify({ message: `Gmail authorized as ${frame.email}`, variant: "success" });
        onSaved();
      } else if (frame.event === "error") {
        setPhase("error");
        setStatusText(frame.text || "authorization failed");
        setBusy(false);
        notify({ message: frame.text || "Gmail auth failed", variant: "error", duration: 5000 });
      }
    });
    return () => {
      mounted.current = false;
      unlistenPromise.then((f) => f()).catch(() => {});
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
        <label className={styles.label}>Client ID</label>
        <input
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
        <label className={styles.label}>Client Secret</label>
        <input
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
        <label className={styles.label}>Allowed senders</label>
        <input
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
          className={styles.muted}
          style={{
            marginTop: "var(--space-2)",
            color:
              phase === "error"
                ? "var(--color-error, #f87171)"
                : phase === "done"
                  ? "var(--color-ok, #4ade80)"
                  : undefined,
          }}
        >
          {statusText}
        </div>
      )}
      <div className={styles.actions}>
        {config?.GMAIL_CLIENT_ID && !busy && (
          <ConfirmButton
            size="sm"
            label="Remove"
            confirmLabel="Confirm"
            onConfirm={remove}
          />
        )}
        <Button size="sm" onClick={onClose}>
          {busy ? "Cancel" : "Close"}
        </Button>
        {!busy && (
          <Button size="sm" variant="primary" onClick={authorize}>
            {config?.GMAIL_CLIENT_ID ? "Re-authorize" : "Authorize"}
          </Button>
        )}
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
      invoke("daemon_restart").catch(() => {});
      notify({
        message: `${gateway} saved · daemon restarting`,
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
            <label className={styles.label}>
              {f.label}
              {f.required && <span aria-hidden="true"> *</span>}
            </label>
            <input
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
      <div className={styles.actions}>
        {isConfigured && (
          <ConfirmButton
            size="sm"
            label="Remove"
            confirmLabel="Confirm"
            loading={busy}
            onConfirm={remove}
          />
        )}
        <Button size="sm" onClick={onClose} disabled={busy}>Close</Button>
        <Button size="sm" variant="primary" onClick={save} loading={busy}>
          Save
        </Button>
      </div>
    </Modal>
  );
}

export function SchedulesSection({ profile }) {
  const [jobs, setJobs] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const notify = useNotify();

  async function load() {
    try {
      const list = await invoke("schedules", { profile: profile.name });
      setJobs(Array.isArray(list) ? list : []);
    } catch {
      setJobs([]);
    }
  }

  useEffect(() => { load(); }, [profile.name]);

  async function fire(id) {
    setBusyId(`fire:${id}`);
    try {
      await invoke("schedule_fire", { profile: profile.name, id });
      notify({ message: `fired ${id}`, variant: "success", duration: 2400 });
      await load();
    } catch (e) {
      notify({ message: `fire failed: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setBusyId(null);
    }
  }

  async function setPaused(id, paused) {
    setBusyId(`pause:${id}`);
    try {
      await invoke("schedule_set_paused", { profile: profile.name, id, paused });
      await load();
    } catch (e) {
      notify({
        message: `${paused ? "pause" : "resume"} failed: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setBusyId(null);
    }
  }

  async function remove(id) {
    setBusyId(`del:${id}`);
    try {
      await invoke("schedule_remove", { profile: profile.name, id });
      await load();
    } catch (e) {
      notify({ message: `delete failed: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setBusyId(null);
    }
  }

  if (jobs === null || jobs.length === 0) return null;
  return (
    <Section title="Schedule">
      {jobs.map((j) => (
        <Row key={j.id} label={j.id}>
          <ScheduleRowBody
            job={j}
            busyId={busyId}
            onFire={() => fire(j.id)}
            onTogglePause={() => setPaused(j.id, !j.paused)}
            onRemove={() => remove(j.id)}
          />
        </Row>
      ))}
    </Section>
  );
}

function ScheduleRowBody({ job, busyId, onFire, onTogglePause, onRemove }) {
  const fireBusy = busyId === `fire:${job.id}`;
  const pauseBusy = busyId === `pause:${job.id}`;
  const delBusy = busyId === `del:${job.id}`;
  const anyBusy = !!busyId;
  const tooltip = (
    <>
      <div>{scheduleSummary(job)}</div>
      <div className={styles.tooltipStatus}>
        {[
          job.paused ? "paused" : "active",
          job.platform || "telegram",
          job.chat_id || null,
          job.last_run_at ? `last ${job.last_run_at}` : null,
        ]
          .filter(Boolean)
          .join(" · ")}
      </div>
    </>
  );
  return (
    <span
      className={`${styles.inlineRow} ${styles.inlineRowSpaceBetween} ${styles.flexFill}`}
    >
      <span className={`${styles.inlineRow} ${styles.flexFill}`}>
        <Chip state={job.paused ? "off" : "on"} tooltip={tooltip}>
          {scheduleSummary(job)}
        </Chip>
        <span
          style={{
            fontSize: "var(--font-size-small)",
            color: "var(--color-fg-muted)",
            opacity: job.paused ? 0.55 : 1,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
            minWidth: 0,
            flex: 1,
          }}
          title={job.prompt || ""}
        >
          {job.prompt || ""}
        </span>
      </span>
      <span className={styles.btnGroup}>
        <Button size="sm" onClick={onFire} loading={fireBusy} disabled={anyBusy}>
          Fire
        </Button>
        <Button size="sm" onClick={onTogglePause} loading={pauseBusy} disabled={anyBusy}>
          {job.paused ? "Enable" : "Disable"}
        </Button>
        <ConfirmButton
          size="sm"
          label="Delete"
          confirmLabel="Confirm"
          disabled={anyBusy && !delBusy}
          loading={delBusy}
          onConfirm={onRemove}
        />
      </span>
    </span>
  );
}
