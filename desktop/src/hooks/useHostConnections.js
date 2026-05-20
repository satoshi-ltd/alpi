import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

import { pruneCachedMessages } from "../lib/workgroup-cache.js";

const PROFILES_CACHE_PREFIX = "alf:profiles:v1:";
const WORKGROUPS_CACHE_PREFIX = "alf:workgroups:v1:";

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
  setPendingTurn,
  setRewriteDraft,
  setActiveTask,
  setView,
  pendingTurnRef,
}) {
  const [hostConnections, setHostConnections] = useState({
    active_id: "local",
    connections: [],
  });
  const [profiles, setProfiles] = useState([]);
  const [workgroups, setWorkgroups] = useState([]);
  const [pickerAlpi, setPickerAlpi] = useState(null);

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

  const applyProfilesAndWorkgroups = useCallback((ps, ws) => {
    setProfiles(ps);
    setWorkgroups(ws);
    pruneCachedMessages(hostConnectionsRef.current?.active_id, ws);
    setPickerAlpi((prev) => {
      if (prev && ps.some((p) => p.name === prev)) return prev;
      const def = ps.find((p) => p.is_default && p.model);
      if (def) return def.name;
      const firstWithModel = ps.find((p) => p.model);
      if (firstWithModel) return firstWithModel.name;
      return ps[0]?.name ?? null;
    });
  }, []);

  const clearConnectionContent = useCallback(() => {
    applyProfilesAndWorkgroups([], []);
    setSessionData(null);
    setPendingTurn(null);
    setRewriteDraft(null);
    setActiveTask(null);
    setView((v) => (v.kind === "settings" ? v : { kind: "empty" }));
  }, [
    applyProfilesAndWorkgroups,
    setSessionData,
    setPendingTurn,
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
      if (status === "offline" || status === "auth-failed") {
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
    const active = cur?.connections?.find((c) => c.id === cur.active_id);
    const status = active?.status;
    if (status !== "online") {
      showCachedOrClear(activeId, status);
      reloadConnections();
      return;
    }
    try {
      let [ps, ws] = await Promise.all([
        invoke("profile_summaries"),
        invoke("workgroups", { profile: null }),
      ]);
      if (Array.isArray(ps) && ps.length === 0) {
        const fallbackProfiles = await invoke("profiles");
        if (Array.isArray(fallbackProfiles) && fallbackProfiles.length > 0) {
          ps = fallbackProfiles;
        }
      }
      // Detail is now LAZY: settings/profile screens fetch host.profile.detail on demand (see useProfileDetail). Reloading every profile's detail on each status flip would re-introduce the very 30–60 KB Tailscale poll we just split apart.
      if (hostConnectionsRef.current?.active_id !== activeId) return;
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
      if (hostConnectionsRef.current?.active_id === activeId) {
        showCachedOrClear(
          activeId,
          hostConnectionsRef.current?.connections?.find((c) => c.id === activeId)
            ?.status,
        );
      }
    } finally {
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
    const off = listen("connection-status", (event) => {
      const { id, status, error, alpi_version } = event.payload ?? {};
      if (!id || !status) return;
      setHostConnections((prev) => {
        const before = prev.connections.find((c) => c.id === id);
        if (
          before &&
          before.status === status &&
          before.error === error &&
          before.alpi_version === (alpi_version ?? null)
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
                }
              : c,
          ),
        };
        hostConnectionsRef.current = next;
        return next;
      });
    });
    return () => {
      off.then((fn) => fn());
    };
  }, []);

  const activeConnectionForSync = hostConnections.connections.find(
    (c) => c.id === hostConnections.active_id,
  );
  const activeStatusKey = `${hostConnections.active_id}:${activeConnectionForSync?.status ?? "unknown"}:${activeConnectionForSync?.error ?? ""}`;

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
    } else if (status === "offline" || status === "auth-failed") {
      reloadConnections().finally(() => clearConnectionContent());
    }
  }, [activeStatusKey, clearConnectionContent, reload, reloadConnections]);

  useEffect(() => {
    reload();
    invoke("host_connections_probe_active").catch(() => {});
  }, [reload, reloadConnections]);

  // Probe runs fire-and-forget; awaiting it locks the UI for 8-16s on slow remotes.
  const onSetHostConnection = useCallback(
    (id) => {
      const current = hostConnectionsRef.current;
      if (current.active_id === id) return;
      const previousState = current;
      const switchId = ++connectionSwitchRef.current;
      const pending = pendingTurnRef.current;
      if (pending?.profile) {
        invoke("chat_cancel", { profile: pending.profile }).catch(() => {});
      }
      setRewriteDraft(null);
      setSessionData(null);
      setPendingTurn(null);
      setActiveTask(null);
      setView((v) => (v.kind === "settings" ? v : { kind: "empty" }));
      loadFromCache(id);
      setHostConnections((prev) => {
        if (prev.active_id === id) return prev;
        const next = {
          ...prev,
          active_id: id,
          connections: prev.connections.map((c) =>
            c.id === id ? { ...c, status: "probing", error: null } : c,
          ),
        };
        hostConnectionsRef.current = next;
        return next;
      });
      syncedStatusRef.current = `${id}:probing:`;

      invoke("host_connection_set_active", { id })
        .then(() => {
          if (connectionSwitchRef.current !== switchId) return;
          invoke("host_connection_probe", { id }).catch(() => {});
        })
        .catch(() => {
          if (connectionSwitchRef.current === switchId) {
            hostConnectionsRef.current = previousState;
            setHostConnections(previousState);
            loadFromCache(previousState.active_id);
          }
          reloadConnections();
        });
    },
    [
      loadFromCache,
      reloadConnections,
      pendingTurnRef,
      setRewriteDraft,
      setSessionData,
      setPendingTurn,
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
    workgroups,
    pickerAlpi,
    setPickerAlpi,
    reload,
    onSetHostConnection,
    onAddHostConnection,
    onForgetHostConnection,
    onRefreshHostConnectionStatus,
  };
}
