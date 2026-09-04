import { useCallback, useEffect, useRef, useState } from "react";
import { stampLastActive } from "../lib/connection-recency.js";
import { invoke } from "@tauri-apps/api/core";

import { pruneCachedMessages } from "../lib/workgroup-cache.js";
import { subscribe } from "../lib/daemon-bus.js";
import { purgeConnectionStorage } from "../lib/connection-gc.js";
import { invalidateConnectionCaches } from "../lib/swr-cache.js";
import {
  invalidateTranscriptCache,
  invalidateWorkgroupTranscriptCache,
} from "../lib/workgroup-fetch.js";
import { invalidateSessionCache } from "../lib/session-cache.js";
import { invalidateProfileDetailCache } from "./useProfileDetail.js";
import { purgeConnectionReadState } from "./useReadState.js";

const PROFILES_CACHE_PREFIX = "alf:profiles:v1:";
const WORKGROUPS_CACHE_PREFIX = "alf:workgroups:v1:";
const TRANSIENT_CACHE_PREFIXES = [
  "alpi.session.cache.v1.",
  "alpi.workgroup.cache.",
];
const OFFLINE_REPROBE_MIN_MS = 4000;
const OFFLINE_REPROBE_MAX_MS = 60000;

function parsePairingPayload(payload) {
  const text = payload.trim();
  if (text.startsWith("alpi://device?")) {
    const url = new URL(text);
    const endpointUrl = url.searchParams.get("url");
    const legacyHost = url.searchParams.get("host");
    const legacyPort = Number(url.searchParams.get("port"));
    return {
      url: endpointUrl || (legacyHost && legacyPort ? `ws://${legacyHost}:${legacyPort}` : ""),
      name: url.searchParams.get("name"),
      token: url.searchParams.get("token"),
      pairingToken: url.searchParams.get("pairing_token"),
    };
  }
  const parsed = JSON.parse(text);
  const endpointUrl = parsed.u ?? parsed.url;
  const legacyHost = parsed.i ?? parsed.ip;
  const legacyPort = Number(parsed.p ?? parsed.port);
  return {
    url: endpointUrl || (legacyHost && legacyPort ? `ws://${legacyHost}:${legacyPort}` : ""),
    name: parsed.n ?? parsed.name,
    token: parsed.t ?? parsed.token,
    pairingToken: parsed.g ?? parsed.pairing_token,
  };
}

export function useHostConnections({
  setSessionData,
  clearTurnsForConnection,
  setRewriteDraft,
  setActiveTask,
  setView,
  notify,
}) {
  const [hostConnections, setHostConnections] = useState({
    active_id: "local",
    connections: [],
  });
  const [profiles, setProfiles] = useState([]);
  const [workgroups, setWorkgroups] = useState([]);
  const [pickerAlpi, setPickerAlpi] = useState(null);
  const [connectionSyncing, setConnectionSyncing] = useState(false);
  const [switchTargetId, setSwitchTargetId] = useState(null);
  useEffect(() => {
    if (!connectionSyncing) setSwitchTargetId(null);
  }, [connectionSyncing]);

  const hostConnectionsRef = useRef(hostConnections);
  const connectionSwitchRef = useRef(0);
  const syncedStatusRef = useRef("");

  const reloadConnections = useCallback(async ({ acceptActiveChange = false } = {}) => {
    const switchId = connectionSwitchRef.current;
    const expectedActiveId = hostConnectionsRef.current?.active_id ?? "local";
    try {
      const value = await invoke("host_connections");
      if (connectionSwitchRef.current !== switchId) return null;
      const current = hostConnectionsRef.current;
      if (
        !acceptActiveChange &&
        current?.connections?.length > 0 &&
        value?.active_id !== expectedActiveId
      ) {
        return null;
      }
      hostConnectionsRef.current = value;
      setHostConnections(value);
      return value;
    } catch {
      return null;
    }
  }, []);

  // Local mtime patch for background workgroup activity — keeps the sidebar's unread dot and recency order truthful without a per-post workgroups RPC. Capped at one patch per second per workgroup.
  const touchWorkgroup = useCallback((profile, wgId) => {
    const now = Math.floor(Date.now() / 1000);
    setWorkgroups((rows) => {
      let changed = false;
      const next = rows.map((w) => {
        if (w.id !== wgId || w.profile !== profile) return w;
        if ((w.mtime ?? 0) >= now) return w;
        changed = true;
        return { ...w, mtime: now };
      });
      return changed ? next : rows;
    });
  }, []);

  const applyProfilesAndWorkgroups = useCallback((ps, ws) => {
    setProfiles(ps);
    setWorkgroups(ws);
    pruneCachedMessages(hostConnectionsRef.current?.active_id, ws);
    setPickerAlpi((prev) => {
      if (prev && ps.some((p) => p.name === prev && !p.paused)) return prev;
      const def = ps.find((p) => p.is_default && p.model && !p.paused);
      if (def) return def.name;
      const firstWithModel = ps.find((p) => p.model && !p.paused);
      if (firstWithModel) return firstWithModel.name;
      return ps.find((p) => !p.paused)?.name ?? null;
    });
  }, []);

  const clearConnectionContent = useCallback(() => {
    applyProfilesAndWorkgroups([], []);
    setSessionData(null);
    clearTurnsForConnection(hostConnectionsRef.current?.active_id ?? null);
    setRewriteDraft(null);
    setActiveTask(null);
    setView((v) => (v.kind === "settings" ? v : { kind: "empty" }));
  }, [
    applyProfilesAndWorkgroups,
    setSessionData,
    clearTurnsForConnection,
    setRewriteDraft,
    setActiveTask,
    setView,
  ]);

  const loadFromCache = useCallback(
    (connectionId = null) => {
      const activeId =
        connectionId ?? hostConnectionsRef.current?.active_id ?? "local";
      try {
        const cachedPs = JSON.parse(
          localStorage.getItem(`${PROFILES_CACHE_PREFIX}${activeId}`) ?? "[]",
        );
        const cachedWs = JSON.parse(
          localStorage.getItem(`${WORKGROUPS_CACHE_PREFIX}${activeId}`) ?? "[]",
        );
        const ps = Array.isArray(cachedPs) ? cachedPs : [];
        const ws = Array.isArray(cachedWs) ? cachedWs : [];
        applyProfilesAndWorkgroups(ps, ws);
      } catch {}
    },
    [applyProfilesAndWorkgroups],
  );

  const saveToCache = useCallback((connectionId, ps, ws) => {
    const profilesKey = `${PROFILES_CACHE_PREFIX}${connectionId}`;
    const workgroupsKey = `${WORKGROUPS_CACHE_PREFIX}${connectionId}`;
    const serializedProfiles = JSON.stringify(ps);
    const serializedWorkgroups = JSON.stringify(ws);
    const write = () => {
      localStorage.setItem(workgroupsKey, serializedWorkgroups);
      localStorage.setItem(profilesKey, serializedProfiles);
    };
    try {
      write();
      return;
    } catch (error) {
      if (error?.name !== "QuotaExceededError") return;
    }
    try {
      const disposable = [];
      for (let i = 0; i < localStorage.length; i += 1) {
        const key = localStorage.key(i);
        if (key && TRANSIENT_CACHE_PREFIXES.some((prefix) => key.startsWith(prefix))) {
          disposable.push(key);
        }
      }
      for (const key of disposable) localStorage.removeItem(key);
      write();
    } catch {}
  }, []);

  const dropWorkgroup = useCallback((connectionId, profile, wgId) => {
    const targetId = connectionId || "local";
    if (hostConnectionsRef.current?.active_id !== targetId) return;
    invalidateWorkgroupTranscriptCache(targetId, profile, wgId);
    setWorkgroups((rows) => {
      const next = rows.filter((w) => w.profile !== profile || w.id !== wgId);
      if (next.length === rows.length) return rows;
      saveToCache(targetId, profiles, next);
      pruneCachedMessages(targetId, next);
      return next;
    });
  }, [profiles, saveToCache]);

  const showCachedOrClear = useCallback(
    (connectionId, status) => {
      if (status === "auth-failed") {
        clearConnectionContent();
      } else {
        loadFromCache(connectionId);
      }
    },
    [clearConnectionContent, loadFromCache],
  );

  const reload = useCallback(async () => {
    const cur = hostConnectionsRef.current;
    const activeId = cur?.active_id ?? "local";
    const switchId = connectionSwitchRef.current;
    const active = cur?.connections?.find((c) => c.id === cur.active_id);
    const status = active?.status;
    if (status !== "online") {
      showCachedOrClear(activeId, status);
      if (status === "offline" || status === "disabled" || status === "auth-failed") {
        setConnectionSyncing(false);
      }
      reloadConnections();
      return;
    }
    setConnectionSyncing(true);
    try {
      let [ps, ws] = await Promise.all([
        invoke("profile_summaries", { connectionId: activeId }),
        invoke("workgroups", { profile: null, connectionId: activeId }),
      ]);
      if (activeId === "local" && Array.isArray(ps) && ps.length === 0) {
        const fallbackProfiles = await invoke("profiles");
        if (Array.isArray(fallbackProfiles) && fallbackProfiles.length > 0) {
          ps = fallbackProfiles;
        }
      }
      // switchId guards A→B→A races where active_id alone would match
      if (
        hostConnectionsRef.current?.active_id !== activeId ||
        connectionSwitchRef.current !== switchId
      ) {
        return;
      }
      const looksLikeFailure =
        Array.isArray(ps) && Array.isArray(ws) && ps.length === 0 && ws.length === 0;
      const refreshed = hostConnectionsRef.current?.connections?.find(
        (c) => c.id === hostConnectionsRef.current?.active_id,
      );
      if (looksLikeFailure && refreshed?.status && refreshed.status !== "online") {
        showCachedOrClear(activeId, refreshed.status);
      } else {
        applyProfilesAndWorkgroups(ps, ws);
        saveToCache(activeId, ps, ws);
      }
    } catch {
      if (
        hostConnectionsRef.current?.active_id === activeId &&
        connectionSwitchRef.current === switchId
      ) {
        showCachedOrClear(
          activeId,
          hostConnectionsRef.current?.connections?.find((c) => c.id === activeId)
            ?.status,
        );
      }
    } finally {
      if (
        hostConnectionsRef.current?.active_id === activeId &&
        connectionSwitchRef.current === switchId
      ) {
        setConnectionSyncing(false);
      }
      reloadConnections();
    }
  }, [
    applyProfilesAndWorkgroups,
    reloadConnections,
    saveToCache,
    showCachedOrClear,
  ]);

  useEffect(() => {
    return subscribe("connection-status", (event) => {
      const { id, status, error, alpi_version, update_available, role } = event.payload ?? {};
      if (!id || !status) return;
      setHostConnections((prev) => {
        const before = prev.connections.find((c) => c.id === id);
        // A null role means "unchanged" (offline/status-only events don't re-probe the role) — never let it clear a role we already know.
        const nextRole = role ?? before?.role ?? null;
        if (
          before &&
          before.status === status &&
          before.error === error &&
          before.alpi_version === (alpi_version ?? null) &&
          before.update_available === (update_available ?? null) &&
          (before.role ?? null) === nextRole
        ) {
          return prev;
        }
        const next = {
          ...prev,
          connections: prev.connections.map((c) =>
            c.id === id
              ? {
                  ...c,
                  status,
                  error: error ?? null,
                  alpi_version: alpi_version ?? null,
                  update_available: update_available ?? null,
                  role: role ?? c.role ?? null,
                }
              : c,
          ),
        };
        hostConnectionsRef.current = next;
        return next;
      });
    });
  }, []);

  const activeConnectionForSync = hostConnections.connections.find(
    (c) => c.id === hostConnections.active_id,
  );
  // Status only (no error): the error string flapping during a restart must not re-fire reload/reprobe effects.
  const activeStatusKey = `${hostConnections.active_id}:${activeConnectionForSync?.status ?? "unknown"}`;

  useEffect(() => {
    const active = hostConnectionsRef.current.connections.find(
      (c) => c.id === hostConnectionsRef.current.active_id,
    );
    const status = active?.status;
    if (syncedStatusRef.current === activeStatusKey) return;
    syncedStatusRef.current = activeStatusKey;
    if (status === "online") {
      reloadConnections().finally(() => reload());
    } else if (status === "auth-failed") {
      setConnectionSyncing(false);
      reloadConnections().finally(() => clearConnectionContent());
    } else if (status === "offline" || status === "disabled") {
      setConnectionSyncing(false);
      reloadConnections().finally(() => loadFromCache(hostConnectionsRef.current.active_id));
    }
  }, [activeStatusKey, clearConnectionContent, loadFromCache, reload, reloadConnections]);

  useEffect(() => {
    reload();
    invoke("host_connections_probe_active").catch(() => {});
  }, [reload, reloadConnections]);

  // Offline has no liveness stream to recover on; terminal authentication states wait for user or host action.
  useEffect(() => {
    const status = activeConnectionForSync?.status;
    if (status !== "offline" && status !== "unknown") return undefined;
    // Backoff resets to 4s each offline period — the effect re-runs on status change, bounding the recursion to one continuous outage.
    let delay = OFFLINE_REPROBE_MIN_MS;
    let timer = null;
    const jitter = (ms) => ms * (0.8 + Math.random() * 0.4);
    const tick = () => {
      invoke("host_connections_probe_active").catch(() => {});
      delay = Math.min(delay * 2, OFFLINE_REPROBE_MAX_MS);
      timer = setTimeout(tick, jitter(delay));
    };
    timer = setTimeout(tick, jitter(delay));
    return () => { if (timer) clearTimeout(timer); };
  }, [activeStatusKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // Probe runs fire-and-forget; awaiting it locks the UI for 8-16s on slow remotes.
  const onSetHostConnection = useCallback(
    (id) => {
      const current = hostConnectionsRef.current;
      if (current.active_id === id) return;
      stampLastActive(id);
      const previousState = current;
      const switchId = ++connectionSwitchRef.current;
      // ref + state must flip BEFORE loadFromCache — pruneCachedMessages reads hostConnectionsRef
      const next = {
        ...previousState,
        active_id: id,
        connections: previousState.connections.map((c) =>
          c.id === id ? { ...c, status: "probing", error: null } : c,
        ),
      };
      hostConnectionsRef.current = next;
      setHostConnections(next);
      setRewriteDraft(null);
      setSessionData(null);
      setActiveTask(null);
      setView((v) => (v.kind === "settings" ? v : { kind: "empty" }));
      setPickerAlpi(null);
      loadFromCache(id);
      setSwitchTargetId(id);
      setConnectionSyncing(true);

      invoke("host_connection_set_active", { id })
        .then(() => {
          if (connectionSwitchRef.current !== switchId) return;
          invoke("host_connection_probe", { id })
            .then((status) => {
              if (connectionSwitchRef.current !== switchId) return;
              if (status === "online") {
                reloadConnections().finally(() => reload());
              } else if (status === "offline" || status === "disabled" || status === "auth-failed") {
                setConnectionSyncing(false);
              }
            })
            .catch(() => {
              if (connectionSwitchRef.current === switchId) setConnectionSyncing(false);
            });
        })
        .catch((e) => {
          if (connectionSwitchRef.current === switchId) {
            hostConnectionsRef.current = previousState;
            setHostConnections(previousState);
            setPickerAlpi(null);
            loadFromCache(previousState.active_id);
            setConnectionSyncing(false);
            notify?.({
              message: String(e).includes("revoked")
                ? "This device's pairing was revoked — re-pair to reconnect."
                : "Could not switch connection.",
              variant: "error",
              duration: 5000,
            });
          }
          reloadConnections();
        });
    },
    [
      loadFromCache,
      reload,
      reloadConnections,
      setRewriteDraft,
      setSessionData,
      setActiveTask,
      setView,
    ],
  );

  const onAddHostConnection = useCallback(
    async (payload) => {
      const { url, name, token, pairingToken } = parsePairingPayload(payload);
      if (!url || (!token && !pairingToken)) {
        throw new Error("pairing payload needs a URL and pairing credential");
      }
      const resolvedName = name ?? new URL(url).hostname;
      await invoke("host_connection_add_remote", {
        name: resolvedName,
        url,
        ...(token ? { token } : {}),
        ...(pairingToken ? { pairingToken } : {}),
      });
      await reloadConnections({ acceptActiveChange: true });
      invoke("host_connections_probe_active").catch(() => {});
      return { name: resolvedName };
    },
    [reloadConnections],
  );

  const onForgetHostConnection = useCallback(
    async (id) => {
      try {
        await invoke("host_connection_forget", { id });
        purgeConnectionStorage(id);
        purgeConnectionReadState(id);
        invalidateConnectionCaches(id);
        invalidateProfileDetailCache(id);
        invalidateTranscriptCache(id);
        invalidateSessionCache(id);
        await reloadConnections({ acceptActiveChange: true });
        await reload();
      } catch {}
    },
    [reload, reloadConnections],
  );

  const onRefreshHostConnectionStatus = useCallback(async () => {
    await invoke("host_connections_probe_all");
  }, []);

  return {
    hostConnections,
    hostConnectionsRef,
    profiles,
    setProfiles,
    workgroups,
    dropWorkgroup,
    connectionSyncing,
    connectionSwitching: switchTargetId != null && connectionSyncing,
    touchWorkgroup,
    pickerAlpi,
    setPickerAlpi,
    reload,
    onSetHostConnection,
    onAddHostConnection,
    onForgetHostConnection,
    onRefreshHostConnectionStatus,
  };
}
