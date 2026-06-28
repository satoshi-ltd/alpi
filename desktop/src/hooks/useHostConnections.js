import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

import { pruneCachedMessages } from "../lib/workgroup-cache.js";
import { safeUnlisten } from "../lib/tauri-listen.js";

const PROFILES_CACHE_PREFIX = "alf:profiles:v1:";
const WORKGROUPS_CACHE_PREFIX = "alf:workgroups:v1:";
const OFFLINE_REPROBE_MS = 4000;

function parsePairingPayload(payload) {
  const text = payload.trim();
  if (text.startsWith("alpi://device?")) {
    const url = new URL(text);
    return {
      host: url.searchParams.get("host"),
      port: Number(url.searchParams.get("port")),
      name: url.searchParams.get("name"),
      token: url.searchParams.get("token"),
    };
  }
  const parsed = JSON.parse(text);
  return {
    host: parsed.i ?? parsed.ip,
    port: Number(parsed.p ?? parsed.port),
    name: parsed.n ?? parsed.name,
    token: parsed.t ?? parsed.token,
  };
}

// Connection switcher state + per-connection profile/workgroup cache; App.jsx passes its own setters (chat/view) so the hook can reset them on connection switch.
export function useHostConnections({
  setSessionData,
  clearAllTurns,
  setRewriteDraft,
  setActiveTask,
  setView,
  pendingTurnsRef,
}) {
  const [hostConnections, setHostConnections] = useState({
    active_id: "local",
    connections: [],
  });
  const [profiles, setProfiles] = useState([]);
  const [workgroups, setWorkgroups] = useState([]);
  const [pickerAlpi, setPickerAlpi] = useState(null);
  const [connectionSyncing, setConnectionSyncing] = useState(false);

  const hostConnectionsRef = useRef(hostConnections);
  const connectionSwitchRef = useRef(0);
  const syncedStatusRef = useRef("");

  const reloadConnections = useCallback(async () => {
    try {
      const value = await invoke("host_connections");
      hostConnectionsRef.current = value;
      setHostConnections(value);
    } catch {}
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
    clearAllTurns();
    setRewriteDraft(null);
    setActiveTask(null);
    setView((v) => (v.kind === "settings" ? v : { kind: "empty" }));
  }, [
    applyProfilesAndWorkgroups,
    setSessionData,
    clearAllTurns,
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
    try {
      localStorage.setItem(
        `${PROFILES_CACHE_PREFIX}${connectionId}`,
        JSON.stringify(ps),
      );
      localStorage.setItem(
        `${WORKGROUPS_CACHE_PREFIX}${connectionId}`,
        JSON.stringify(ws),
      );
    } catch {}
  }, []);

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
      if (status === "offline" || status === "auth-failed") setConnectionSyncing(false);
      reloadConnections();
      return;
    }
    setConnectionSyncing(true);
    try {
      let [ps, ws] = await Promise.all([
        invoke("profile_summaries", { connectionId: activeId }),
        invoke("workgroups", { profile: null, connectionId: activeId }),
      ]);
      if (Array.isArray(ps) && ps.length === 0) {
        const fallbackProfiles = await invoke("profiles");
        if (Array.isArray(fallbackProfiles) && fallbackProfiles.length > 0) {
          ps = fallbackProfiles;
        }
      }
      // Detail is now LAZY: settings/profile screens fetch host.profile.detail on demand (see useProfileDetail). Reloading every profile's detail on each status flip would re-introduce the very 30–60 KB Tailscale poll we just split apart.
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

  // Forward connection-status events from the daemon into local state.
  useEffect(() => {
    let cancelled = false;
    let unlisten = null;
    listen("connection-status", (event) => {
      const { id, status, error, alpi_version, update_available } = event.payload ?? {};
      if (!id || !status) return;
      setHostConnections((prev) => {
        const before = prev.connections.find((c) => c.id === id);
        if (
          before &&
          before.status === status &&
          before.error === error &&
          before.alpi_version === (alpi_version ?? null) &&
          before.update_available === (update_available ?? null)
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
                }
              : c,
          ),
        };
        hostConnectionsRef.current = next;
        return next;
      });
    })
      .then((fn) => {
        if (cancelled) safeUnlisten(fn);
        else unlisten = fn;
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      safeUnlisten(unlisten);
    };
  }, []);

  const activeConnectionForSync = hostConnections.connections.find(
    (c) => c.id === hostConnections.active_id,
  );
  // Status only (no error): the error string flapping during a restart must not re-fire reload/reprobe effects.
  const activeStatusKey = `${hostConnections.active_id}:${activeConnectionForSync?.status ?? "unknown"}`;

  // React to status transitions (online → reload, offline → clear).
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
    } else if (status === "offline") {
      setConnectionSyncing(false);
      reloadConnections().finally(() => loadFromCache(hostConnectionsRef.current.active_id));
    }
  }, [activeStatusKey, clearConnectionContent, loadFromCache, reload, reloadConnections]);

  useEffect(() => {
    reload();
    invoke("host_connections_probe_active").catch(() => {});
  }, [reload, reloadConnections]);

  // Offline has no liveness stream to recover on, so re-probe until the daemon returns (makes the pill's "retrying…" real); auth-failed is excluded — a revoked token won't fix itself.
  useEffect(() => {
    const status = activeConnectionForSync?.status;
    if (status !== "offline" && status !== "unknown") return undefined;
    const timer = setInterval(() => {
      invoke("host_connections_probe_active").catch(() => {});
    }, OFFLINE_REPROBE_MS);
    return () => clearInterval(timer);
  }, [activeStatusKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // Probe runs fire-and-forget; awaiting it locks the UI for 8-16s on slow remotes.
  const onSetHostConnection = useCallback(
    (id) => {
      const current = hostConnectionsRef.current;
      if (current.active_id === id) return;
      const previousState = current;
      const switchId = ++connectionSwitchRef.current;
      for (const t of Object.values(pendingTurnsRef.current)) {
        if (t.profile) {
          invoke("chat_cancel", { profile: t.profile, requestId: t.requestId }).catch(() => {});
        }
      }
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
      clearAllTurns();
      setActiveTask(null);
      setView((v) => (v.kind === "settings" ? v : { kind: "empty" }));
      // reset picker — applyProfilesAndWorkgroups keeps prev if name collides across connections
      setPickerAlpi(null);
      loadFromCache(id);
      setConnectionSyncing(true);

      invoke("host_connection_set_active", { id })
        .then(() => {
          if (connectionSwitchRef.current !== switchId) return;
          invoke("host_connection_probe", { id })
            .then((status) => {
              if (connectionSwitchRef.current !== switchId) return;
              if (status === "online") {
                reloadConnections().finally(() => reload());
              } else if (status === "offline" || status === "auth-failed") {
                setConnectionSyncing(false);
              }
            })
            .catch(() => {
              if (connectionSwitchRef.current === switchId) setConnectionSyncing(false);
            });
        })
        .catch(() => {
          if (connectionSwitchRef.current === switchId) {
            hostConnectionsRef.current = previousState;
            setHostConnections(previousState);
            setPickerAlpi(null);
            loadFromCache(previousState.active_id);
            setConnectionSyncing(false);
          }
          reloadConnections();
        });
    },
    [
      loadFromCache,
      reload,
      reloadConnections,
      pendingTurnsRef,
      setRewriteDraft,
      setSessionData,
      clearAllTurns,
      setActiveTask,
      setView,
    ],
  );

  const onAddHostConnection = useCallback(
    async (payload) => {
      const { host, port, name, token } = parsePairingPayload(payload);
      if (!host || !port || !token) {
        throw new Error("pairing payload needs host, port, and token");
      }
      const resolvedName = name ?? host;
      await invoke("host_connection_add_remote", {
        name: resolvedName,
        host,
        port,
        token,
      });
      await reloadConnections();
      invoke("host_connections_probe_active").catch(() => {});
      return { name: resolvedName };
    },
    [reloadConnections],
  );

  const onForgetHostConnection = useCallback(
    async (id) => {
      try {
        await invoke("host_connection_forget", { id });
        await reloadConnections();
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
    connectionSyncing,
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
