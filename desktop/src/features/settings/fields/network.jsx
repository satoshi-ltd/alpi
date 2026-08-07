import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../../primitives/Button.jsx";
import Eyebrow from "../../../primitives/Eyebrow.jsx";
import Chip from "../../../primitives/Chip.jsx";
import ConfirmDelete from "../../../primitives/ConfirmDelete.jsx";
import Field from "../../../primitives/Field.jsx";
import { useNotify } from "../../../primitives/Notification.jsx";
import { useDismissOnOutside } from "../../../hooks/useDismissOnOutside.js";
import { Row } from "../primitives.jsx";
import styles from "../Settings.module.css";

// Coalesce only concurrent probes — no time-cache, each settings open still fetches fresh.
let _statusInflight = null;
const _statusSubscribers = new Set();

function fetchNetworkStatus() {
  if (_statusInflight) return _statusInflight;
  const p = invoke("network_status").finally(() => {
    if (_statusInflight === p) _statusInflight = null;
  });
  _statusInflight = p;
  return p;
}

export function _resetNetworkStatus() {
  _statusInflight = null;
}

function useNetworkStatusSubscription(refresh) {
  useEffect(() => {
    _statusSubscribers.add(refresh);
    return () => _statusSubscribers.delete(refresh);
  }, [refresh]);
}

async function refreshNetworkStatusFields() {
  _resetNetworkStatus();
  await Promise.all([..._statusSubscribers].map((refresh) => refresh()));
}

function routeFor(endpoints, scheme) {
  return (endpoints || []).find((endpoint) => endpoint.url?.startsWith(`${scheme}://`)) || null;
}

function parsePublicRoute(value) {
  const url = value.trim();
  if (!url) return null;
  let parsed;
  try { parsed = new URL(url); } catch { parsed = null; }
  if (
    !parsed
    || parsed.protocol !== "wss:"
    || !parsed.hostname
    || parsed.username
    || parsed.password
    || (parsed.pathname && parsed.pathname !== "/")
    || parsed.search
    || parsed.hash
  ) {
    throw new Error("Use a complete wss:// URL without credentials, paths, query, or fragment.");
  }
  return { label: "Public", url };
}

export function PrivateRouteField({ onLoadingChange = null }) {
  const notify = useNotify();
  const [status, setStatus] = useState(null);

  const refresh = useCallback(async () => {
    onLoadingChange?.(true);
    try {
      setStatus(await fetchNetworkStatus());
    } catch (error) {
      notify({ message: `network: ${String(error)}`, variant: "error" });
    } finally {
      onLoadingChange?.(false);
    }
  }, [notify, onLoadingChange]);

  useEffect(() => { refresh(); }, [refresh]);
  useNetworkStatusSubscription(refresh);

  const supportsEndpoints = Array.isArray(status?.endpoints);
  const endpoint = supportsEndpoints ? routeFor(status.endpoints, "ws") : null;
  const needsRestart = supportsEndpoints
    && !Array.isArray(status?.configured_endpoints)
    && Boolean(routeFor(status.endpoints, "wss"))
    && !endpoint;

  return (
    <Row label="private route">
      <Chip
        state={endpoint ? "on" : "off"}
        tooltip="Direct private-network route derived from the address and listen port"
      >
        {!status
          ? "loading…"
          : !supportsEndpoints || needsRestart
            ? "restart required"
            : endpoint?.url || "unavailable"}
      </Chip>
    </Row>
  );
}

export function PublicRouteField({ onLoadingChange = null }) {
  const notify = useNotify();
  const [open, setOpen] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const wrapRef = useRef(null);
  const [status, setStatus] = useState(null);
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);

  useDismissOnOutside({ open, onClose: () => setOpen(false), wrapRef });

  const refresh = useCallback(async () => {
    onLoadingChange?.(true);
    try {
      const next = await fetchNetworkStatus();
      setStatus(next);
      setValue(routeFor(next?.endpoints, "wss")?.url || "");
    } catch (error) {
      notify({ message: `network: ${String(error)}`, variant: "error" });
    } finally {
      onLoadingChange?.(false);
    }
  }, [notify, onLoadingChange]);

  useEffect(() => { refresh(); }, [refresh]);
  useNetworkStatusSubscription(refresh);

  let endpoint = null;
  let error = "";
  try { endpoint = parsePublicRoute(value); } catch (caught) { error = caught.message; }
  const supportsEndpoints = Array.isArray(status?.endpoints)
    && typeof status?.is_endpoints_override === "boolean";
  const current = supportsEndpoints ? routeFor(status.endpoints, "wss") : null;
  const dirty = Boolean(status) && value.trim() !== (current?.url || "");

  async function save(nextEndpoint = endpoint) {
    if ((nextEndpoint && error) || saving) return;
    setSaving(true);
    try {
      const explicitPrivateRoutes = (status?.configured_endpoints || [])
        .filter((row) => row.url?.startsWith("ws://"));
      await invoke("network_set_advertised", {
        endpoints: nextEndpoint
          ? [nextEndpoint, ...explicitPrivateRoutes]
          : explicitPrivateRoutes,
      });
      notify({
        message: nextEndpoint ? "Public route updated" : "Public route removed",
        variant: "success",
        duration: 2500,
      });
      await refreshNetworkStatusFields();
      setOpen(false);
    } catch (caught) {
      notify({ message: `network: ${String(caught)}`, variant: "error", duration: 4500 });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Row label="public route">
      <span ref={wrapRef} className={styles.popoverAnchor}>
        <span className={styles.inlineRow}>
          <Chip state={current ? "on" : "off"} tooltip="Optional certificate-validated Internet route">
            {!status ? "loading…" : !supportsEndpoints ? "restart required" : current?.url || "off"}
          </Chip>
          {supportsEndpoints && (
            <Button size="sm" onClick={() => setOpen((visible) => !visible)}>
              {current ? "Edit" : "Add"}
            </Button>
          )}
          {supportsEndpoints && current && (
            <span className={styles.confirmAnchor}>
              <Button
                size="sm"
                variant="danger"
                onClick={() => setConfirmRemove(true)}
                loading={saving}
              >
                Remove
              </Button>
              <ConfirmDelete
                open={confirmRemove}
                onClose={() => setConfirmRemove(false)}
                onConfirm={() => save(null)}
                title="Remove public route?"
                consequence="New pairing codes will stop offering this WSS route. Existing paired devices are unchanged."
                confirmLabel="Remove"
              />
            </span>
          )}
        </span>
        {open && (
          <div className={`${styles.popover} ${styles.networkPopover}`}>
            <div className={styles.field}>
              <Eyebrow as="label">public WSS route</Eyebrow>
              <Field
                className={styles.input}
                value={value}
                onChange={(event) => setValue(event.target.value)}
                placeholder="wss://client.example.com"
                aria-label="Public WSS route"
                spellCheck={false}
              />
              <div className={error ? styles.warn : styles.muted}>
                {error || "A TLS proxy must serve this hostname and forward to Alpi's listen port."}
              </div>
            </div>
            <div className={styles.actions}>
              <Button
                size="sm"
                variant="primary"
                onClick={() => save()}
                disabled={!dirty || Boolean(error) || !endpoint}
                loading={saving}
              >
                Save
              </Button>
            </div>
          </div>
        )}
      </span>
    </Row>
  );
}

export function NetworkAddressField({ profile, onSaved, onLoadingChange = null }) {
  const notify = useNotify();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const [status, setStatus] = useState(null);
  const [port, setPort] = useState("");
  const [saving, setSaving] = useState(false);
  const [portFree, setPortFree] = useState(null);

  useDismissOnOutside({ open, onClose: () => setOpen(false), wrapRef });

  const refresh = useCallback(async () => {
    onLoadingChange?.(true);
    try {
      const next = await fetchNetworkStatus();
      setStatus(next);
      setPort(String(next?.port || 49200));
    } catch (error) {
      notify({ message: `network: ${String(error)}`, variant: "error" });
    } finally {
      onLoadingChange?.(false);
    }
  }, [notify, onLoadingChange]);

  useEffect(() => { refresh(); }, [refresh]);
  useNetworkStatusSubscription(refresh);

  const current = status?.port || 49200;
  const address = status?.host_in_use || "no address";
  const environmentManaged = status?.port_source === "environment";
  const source = status?.is_override
    ? "Configured in config.yaml"
    : status?.candidates?.docker
      ? "Provided by the environment"
      : "Detected automatically";
  const portNumber = Number(port.trim());
  const portValid = /^[0-9]+$/.test(port.trim()) && portNumber >= 1 && portNumber <= 65535;
  const dirty = portValid && portNumber !== current;

  useEffect(() => {
    if (!open || !portValid || portNumber === current) {
      setPortFree(null);
      return undefined;
    }
    let cancelled = false;
    const timeout = setTimeout(() => {
      invoke("port_available", {
        host: (profile.advertise_host || "").trim() || "0.0.0.0",
        port: portNumber,
      })
        .then((available) => { if (!cancelled) setPortFree(available); })
        .catch(() => { if (!cancelled) setPortFree(null); });
    }, 350);
    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  }, [open, portNumber, portValid, current, profile.advertise_host]);

  async function save() {
    if (!dirty || saving || portFree === false) return;
    setSaving(true);
    try {
      if (portNumber === 49200) {
        await invoke("unset_config_field", { profile: profile.name, key: "host.tcp_port" });
      } else {
        await invoke("set_config_field", {
          profile: profile.name,
          key: "host.tcp_port",
          value: String(portNumber),
        });
      }
      try {
        await invoke("network_restart_host_server");
      } catch (error) {
        await onSaved?.();
        notify({
          message: `Listen port ${portNumber} saved · restart failed: ${String(error)}`,
          variant: "warn",
          duration: 4500,
        });
        setOpen(false);
        return;
      }
      await onSaved?.();
      notify({
        message: `Listen port ${portNumber} saved · daemon restarting`,
        variant: "success",
        duration: 3000,
      });
      setOpen(false);
    } catch (error) {
      notify({ message: `network: ${String(error)}`, variant: "error", duration: 4500 });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Row label="address">
      <span ref={wrapRef} className={styles.popoverAnchor}>
        <span className={styles.inlineRow}>
          <Chip
            state={status?.host_in_use ? "on" : "off"}
            tooltip={`${source}. The address is read-only.`}
          >
            {!status ? "loading…" : address}
          </Chip>
          <Chip
            state="on"
            tooltip={environmentManaged
              ? "Managed by ALPI_HOST_TCP_PORT and the container port mapping"
              : "WebSocket listener used by Desktop and Mobile"}
          >
            :{current}
          </Chip>
          {!environmentManaged && (
            <Button size="sm" onClick={() => setOpen((value) => !value)}>Edit</Button>
          )}
        </span>
        {open && (
          <div className={styles.popover}>
            <div className={styles.field}>
              <Eyebrow as="label">port</Eyebrow>
              <Field
                className={styles.input}
                value={port}
                onChange={(event) => setPort(event.target.value)}
                placeholder="49200"
                aria-label="Host listen port"
                spellCheck={false}
              />
              <div className={portValid && portFree !== false ? styles.muted : styles.warn}>
                {!portValid
                  ? "Port must be between 1 and 65535."
                  : portFree === false
                    ? `Port ${portNumber} is already in use.`
                    : "Changing the listener requires a daemon restart."}
              </div>
            </div>
            <div className={styles.actions}>
              <Button
                size="sm"
                variant="primary"
                onClick={save}
                disabled={!dirty || portFree === false}
                loading={saving}
              >
                Save and restart
              </Button>
            </div>
          </div>
        )}
      </span>
    </Row>
  );
}

export function PairingNameField({ onLoadingChange = null }) {
  const notify = useNotify();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const [status, setStatus] = useState(null);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);

  useDismissOnOutside({ open, onClose: () => setOpen(false), wrapRef });

  const refresh = useCallback(async () => {
    onLoadingChange?.(true);
    try {
      const s = await fetchNetworkStatus();
      setStatus(s);
      setName(s?.device_name || "");
    } catch (e) {
      notify({ message: `network: ${String(e)}`, variant: "error" });
    } finally {
      onLoadingChange?.(false);
    }
  }, [notify, onLoadingChange]);

  useEffect(() => { refresh(); }, [refresh]);
  useNetworkStatusSubscription(refresh);

  const current = status?.device_name || "";
  const dirty = status ? name.trim() !== current : false;

  async function save() {
    if (!dirty || saving) return;
    setSaving(true);
    try {
      await invoke("network_set_advertised", { deviceName: name.trim() });
      notify({ message: "Instance name updated", variant: "success", duration: 2500 });
      await refreshNetworkStatusFields();
      setOpen(false);
    } catch (e) {
      notify({ message: `network: ${String(e)}`, variant: "error", duration: 4500 });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Row label="name">
      <span ref={wrapRef} className={styles.popoverAnchor}>
        <span className={styles.inlineRow}>
          <Chip state="on" tooltip="Instance name shown to new devices">
            {current || "auto"}
          </Chip>
          <Button size="sm" onClick={() => setOpen((o) => !o)}>Edit</Button>
        </span>
        {open && (
          <div className={styles.popover}>
            <div className={styles.field}>
              <Eyebrow as="label">instance name</Eyebrow>
              <Field
                className={styles.input}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="auto-detect from hostname"
                spellCheck={false}
              />
            </div>
            <div className={styles.actions}>
              <Button size="sm" variant="primary" onClick={save} disabled={!dirty} loading={saving}>
                Save
              </Button>
            </div>
          </div>
        )}
      </span>
    </Row>
  );
}
