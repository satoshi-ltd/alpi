import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";
import AppHeader from "./components/AppHeader.jsx";
import Sidebar from "./components/Sidebar.jsx";
import ChatPane from "./components/ChatPane.jsx";
import WorkgroupView from "./components/WorkgroupView.jsx";
import Settings from "./components/Settings.jsx";
import { useNotify } from "./primitives/Notification.jsx";
import { installUpdater } from "./lib/updater.js";
import { findLatestTask } from "./lib/workgroup-tasks.js";
import {
  loadCachedMessages,
  saveCachedMessages,
} from "./lib/workgroup-cache.js";
import {
  loadTaskCache,
  saveTaskCache,
} from "./lib/workgroup-task-cache.js";
import styles from "./App.module.css";

const PINNED_KEY = "alf:pinned:v1";

function isChatSessionSummary(session) {
  return session?.kind === "chat";
}

function isChatSessionData(data) {
  const first = String(data?.turns?.[0]?.user ?? "").trimStart();
  if (!first) return true;
  if (first.startsWith("[workgroup-poller]") || first.startsWith("[workgroup ")) {
    return false;
  }
  if (first.startsWith("[SCHEDULED:") || first.startsWith("[CRON")) {
    return false;
  }
  if (first.startsWith("[INBOUND ")) return false;
  if (first.startsWith("[")) return false;
  return true;
}

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

function loadPinned() {
  try {
    const raw = localStorage.getItem(PINNED_KEY);
    return raw ? JSON.parse(raw) : { profiles: [], workgroups: [] };
  } catch {
    return { profiles: [], workgroups: [] };
  }
}

export default function App() {
  const [collapsed, setCollapsed] = useState(false);
  const [profiles, setProfiles] = useState([]);
  const [workgroups, setWorkgroups] = useState([]);
  const [hostConnections, setHostConnections] = useState({
    active_id: "local",
    connections: [],
  });
  const [pinned, setPinned] = useState(loadPinned);
  const [view, setView] = useState({ kind: "empty" });
  const [pickerAlpi, setPickerAlpi] = useState(null);
  const [settingsTarget, setSettingsTarget] = useState({
    kind: "profile",
    id: null,
  });
  const [sessionData, setSessionData] = useState(null);
  const [pendingTurn, setPendingTurn] = useState(null);
  const [rewriteDraft, setRewriteDraft] = useState(null);
  const [activeTask, setActiveTask] = useState(null);
  // Restore cached workgroup state on first paint.
  const persistedCache = useMemo(() => loadTaskCache(), []);
  const [taskByWorkgroup, setTaskByWorkgroup] = useState(
    () => persistedCache.tasks,
  );
  // Track the mtime used for each cached task.
  const seenMtimesRef = useRef(persistedCache.mtimes);
  const [activityByWorkgroup, setActivityByWorkgroup] = useState({});
  const [error, setError] = useState(null);
  const notify = useNotify();
  const hostConnectionsRef = useRef(hostConnections);

  const reloadConnections = useCallback(async () => {
    try {
      const value = await invoke("host_connections");
      const prevById = new Map(
        (hostConnectionsRef.current?.connections ?? []).map((c) => [c.id, c]),
      );
      const revoked = (value?.connections ?? []).filter((c) => {
        const before = prevById.get(c.id);
        return c.kind === "remote" && c.revoked && before && !before.revoked;
      });
      if (revoked.length > 0) {
        notify({
          message: `${revoked[0].name} was revoked on the host`,
          variant: "error",
        });
      }
      hostConnectionsRef.current = value;
      setHostConnections(value);
    } catch (e) {
      notify({ message: String(e), variant: "error" });
    }
  }, [notify]);

  const reload = useCallback(async () => {
    try {
      const [ps, ws] = await Promise.all([
        invoke("profile_summaries"),
        invoke("workgroups", { profile: null }),
      ]);
      setProfiles(ps);
      setWorkgroups(ws);
      setError(null);
      setPickerAlpi((prev) => {
        if (prev && ps.some((p) => p.name === prev)) return prev;
        const def = ps.find((p) => p.is_default && p.model);
        if (def) return def.name;
        const firstWithModel = ps.find((p) => p.model);
        if (firstWithModel) return firstWithModel.name;
        return ps[0]?.name ?? null;
      });
    } catch (e) {
      setError(String(e));
    } finally {
      reloadConnections();
    }
  }, [reloadConnections]);

  useEffect(() => {
    reloadConnections();
    reload();
  }, [reload, reloadConnections]);

  const onSetHostConnection = useCallback(
    async (id) => {
      try {
        await invoke("host_connection_set_active", { id });
        await reloadConnections();
        await reload();
      } catch (e) {
        notify({ message: String(e), variant: "error" });
      }
    },
    [notify, reload, reloadConnections],
  );

  const onAddHostConnection = useCallback(
    async (payload) => {
      try {
        const { host, port, name, token } = parsePairingPayload(payload);
        if (!host || !port || !token) {
          throw new Error("pairing payload needs host, port, and token");
        }
        await invoke("host_connection_add_remote", {
          name: name ?? host,
          host,
          port,
          token,
        });
        await reloadConnections();
        await reload();
      } catch (e) {
        notify({ message: String(e), variant: "error" });
      }
    },
    [notify, reload, reloadConnections],
  );

  const onForgetHostConnection = useCallback(
    async (id) => {
      try {
        await invoke("host_connection_forget", { id });
        await reloadConnections();
        await reload();
      } catch (e) {
        notify({ message: String(e), variant: "error" });
      }
    },
    [notify, reload, reloadConnections],
  );

  const onRefreshHostConnectionStatus = useCallback(async () => {
    await invoke("host_connection_refresh_active");
    await reloadConnections();
  }, [reloadConnections]);

  const hubPubkeyOf = useCallback(
    (profileName) =>
      profiles.find((p) => p.name === profileName)?.pubkey_b64 ?? null,
    [profiles],
  );

  // Backfill missing or stale cached tasks from disk.
  useEffect(() => {
    if (workgroups.length === 0) return;
    setTaskByWorkgroup((prev) => {
      let changed = false;
      const next = { ...prev };
      for (const w of workgroups) {
        const key = `${w.profile}/${w.id}`;
        if (next[key]) continue;
        const cached = loadCachedMessages(w.profile, w.id);
        if (cached.length === 0) continue;
        const hubName = w.hub_id ?? w.profile;
        const task = findLatestTask(cached, hubPubkeyOf(hubName));
        if (task == null) continue;
        next[key] = task;
        changed = true;
      }
      return changed ? next : prev;
    });
  }, [workgroups, hubPubkeyOf]);

  // Refresh changed workgroups sequentially to avoid IPC saturation.
  const hubPubkeyOfRef = useRef(hubPubkeyOf);
  useEffect(() => {
    hubPubkeyOfRef.current = hubPubkeyOf;
  }, [hubPubkeyOf]);

  useEffect(() => {
    if (workgroups.length === 0) return;
    let cancelled = false;
    const seen = seenMtimesRef.current;
    const queue = workgroups.filter((w) => {
      const key = `${w.profile}/${w.id}`;
      const last = seen[key] ?? 0;
      const cur = w.mtime ?? 0;
      return cur > last;
    });
    if (queue.length === 0) return;
    async function drain() {
      await new Promise((r) => setTimeout(r, 200));
      for (const w of queue) {
        if (cancelled) return;
        const key = `${w.profile}/${w.id}`;
        const hubName = w.hub_id ?? w.profile;
        try {
          const msgs = await invoke("workgroup_transcript", {
            profile: w.profile,
            wgId: w.id,
          });
          if (cancelled) return;
          if (!Array.isArray(msgs)) continue;
          const hub = hubPubkeyOfRef.current(hubName);
          const task = findLatestTask(msgs, hub);
          setTaskByWorkgroup((prev) =>
            prev[key] === task ? prev : { ...prev, [key]: task },
          );
          seenMtimesRef.current = {
            ...seenMtimesRef.current,
            [key]: w.mtime ?? 0,
          };
          saveCachedMessages(w.profile, w.id, msgs);
        } catch {}
        await new Promise((r) => setTimeout(r, 250));
      }
    }
    drain();
    return () => {
      cancelled = true;
    };
  }, [workgroups]);

  // Persist task cache and mtimes after each update.
  useEffect(() => {
    saveTaskCache({ tasks: taskByWorkgroup, mtimes: seenMtimesRef.current });
  }, [taskByWorkgroup]);

  useEffect(() => {
    return installUpdater();
  }, []);

  useEffect(() => {
    const off = listen("nav", (event) => {
      if (event.payload === "settings") setView({ kind: "settings" });
      else if (event.payload === "home") {
        setView((v) => (v.kind === "settings" ? { kind: "empty" } : v));
      }
    });
    return () => {
      off.then((fn) => fn());
    };
  }, []);

  useEffect(() => {
    function onDown(e) {
      if (e.button !== 0) return;
      const t = e.target;
      if (!(t instanceof Element)) return;
      if (
        t.closest(
          "button, input, textarea, select, a, [contenteditable], [data-no-drag]",
        )
      ) {
        return;
      }
      if (!t.closest("[data-drag]")) return;
      e.preventDefault();
      const win = getCurrentWindow();
      if (e.detail === 2) {
        win.toggleMaximize().catch(() => {});
      } else {
        win.startDragging().catch(() => {});
      }
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  useEffect(() => {
    function onKey(e) {
      const cmd = e.metaKey || e.ctrlKey;
      if (!cmd) return;
      const key = e.key.toLowerCase();
      if (key === "b") {
        if (viewRef.current?.kind === "settings") return;
        e.preventDefault();
        e.stopPropagation();
        setCollapsed((c) => !c);
        return;
      }
      if (key === "n") {
        if (viewRef.current?.kind === "profile") {
          e.preventDefault();
          e.stopPropagation();
          setView((v) => (v.kind === "profile" ? { ...v, sessionId: null } : v));
        }
        return;
      }
      if (key === ",") {
        e.preventDefault();
        e.stopPropagation();
        setView({ kind: "settings" });
      }
    }
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, []);

  useEffect(() => {
    setSessionData(null);
    if (view.kind !== "profile" || !view.sessionId) return;
    invoke("session_detail", { profile: view.profile, id: view.sessionId })
      .then((data) => {
        if (!isChatSessionData(data)) {
          setView((v) =>
            v.kind === "profile" && v.sessionId === view.sessionId
              ? { ...v, sessionId: null }
              : v,
          );
          return;
        }
        setSessionData(data);
      })
      .catch(() => {});
  }, [view]);

  useEffect(() => {
    const COLLAPSE_BELOW = 600;
    const EXPAND_ABOVE = 720;
    function onResize() {
      const w = window.innerWidth;
      if (w < COLLAPSE_BELOW) setCollapsed(true);
      else if (w > EXPAND_ABOVE) setCollapsed(false);
    }
    window.addEventListener("resize", onResize);
    onResize();
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const onNewChat = useCallback(() => {
    setRewriteDraft(null);
    setView({ kind: "empty" });
  }, []);

  const onOpenProfile = useCallback((profile) => {
    setRewriteDraft(null);
    setView({
      kind: "profile",
      profile: profile.name,
      sessionId: isChatSessionSummary(profile.latest_session)
        ? profile.latest_session.id
        : null,
    });
  }, []);

  const onChangeSession = useCallback((sessionId) => {
    setRewriteDraft(null);
    setView((v) => (v.kind === "profile" ? { ...v, sessionId } : v));
  }, []);

  const onNewSessionForCurrentProfile = useCallback(() => {
    setRewriteDraft(null);
    setView((v) => (v.kind === "profile" ? { ...v, sessionId: null } : v));
  }, []);

  const onRewriteMessage = useCallback((profileName, sessionId, turnIndex, text) => {
    if (!profileName || !sessionId || !text) return;
    setRewriteDraft({
      profile: profileName,
      sessionId,
      turnIndex,
      text,
      nonce: Date.now(),
    });
  }, []);

  const onOpenWorkgroup = useCallback((workgroup) => {
    setView({
      kind: "workgroup",
      profile: workgroup.profile,
      id: workgroup.id,
    });
  }, []);

  const onTogglePin = useCallback((kind, key) => {
    setPinned((prev) => {
      const list = prev[kind] ?? [];
      const next = list.includes(key)
        ? list.filter((k) => k !== key)
        : [...list, key];
      const updated = { ...prev, [kind]: next };
      localStorage.setItem(PINNED_KEY, JSON.stringify(updated));
      return updated;
    });
  }, []);

  const activeProfile = useMemo(() => {
    if (view.kind === "profile") {
      return profiles.find((p) => p.name === view.profile) ?? null;
    }
    if (view.kind === "settings" && settingsTarget.kind === "profile") {
      return (
        profiles.find((p) => p.name === settingsTarget.id) ?? profiles[0] ?? null
      );
    }
    if (view.kind === "empty" && pickerAlpi) {
      return profiles.find((p) => p.name === pickerAlpi) ?? null;
    }
    return null;
  }, [view, profiles, pickerAlpi, settingsTarget]);

  const activeSettingsWorkgroup = useMemo(() => {
    if (view.kind !== "settings" || settingsTarget.kind !== "workgroup") {
      return null;
    }
    return workgroups.find((w) => w.id === settingsTarget.id) ?? null;
  }, [view, settingsTarget, workgroups]);

  const reloadRef = useRef(reload);
  useEffect(() => {
    reloadRef.current = reload;
  }, [reload]);

  const viewRef = useRef(view);
  const prevViewRef = useRef(view);
  useEffect(() => {
    if (view.kind !== "settings") prevViewRef.current = view;
    viewRef.current = view;
  }, [view]);

  const closeSettings = useCallback(() => {
    setView(
      prevViewRef.current && prevViewRef.current.kind !== "settings"
        ? prevViewRef.current
        : { kind: "empty" },
    );
  }, []);
  const toggleSidebar = useCallback(() => {
    setCollapsed((c) => !c);
  }, []);

  const profilesRef = useRef(profiles);
  useEffect(() => {
    profilesRef.current = profiles;
  }, [profiles]);

  const pendingTurnRef = useRef(pendingTurn);
  useEffect(() => {
    pendingTurnRef.current = pendingTurn;
  }, [pendingTurn]);

  const reloadTimerRef = useRef(null);
  const scheduleReload = useCallback((delay = 500) => {
    if (reloadTimerRef.current) clearTimeout(reloadTimerRef.current);
    reloadTimerRef.current = setTimeout(() => {
      reloadTimerRef.current = null;
      reloadRef.current?.();
    }, delay);
  }, []);

  const sessionRefreshTimerRef = useRef(null);
  const scheduleSessionRefresh = useCallback((profile, sessionId) => {
    if (sessionRefreshTimerRef.current) {
      clearTimeout(sessionRefreshTimerRef.current);
    }
    sessionRefreshTimerRef.current = setTimeout(() => {
      sessionRefreshTimerRef.current = null;
      invoke("session_detail", { profile, id: sessionId })
        .then((data) => {
          if (isChatSessionData(data)) setSessionData(data);
        })
        .catch(() => {});
    }, 350);
  }, []);

  useEffect(
    () => () => {
      if (reloadTimerRef.current) clearTimeout(reloadTimerRef.current);
      if (sessionRefreshTimerRef.current) {
        clearTimeout(sessionRefreshTimerRef.current);
      }
    },
    [],
  );

  useEffect(() => {
    const id = setInterval(() => {
      const cutoff = Date.now() - 10000;
      setActivityByWorkgroup((prev) => {
        let stale = false;
        for (const ts of Object.values(prev)) {
          if (ts < cutoff) {
            stale = true;
            break;
          }
        }
        if (!stale) return prev;
        const next = {};
        for (const [k, ts] of Object.entries(prev)) {
          if (ts >= cutoff) next[k] = ts;
        }
        return next;
      });
    }, 3000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const off = listen("fs-change", (event) => {
      const ev = event.payload;
      const v = viewRef.current;
      switch (ev.kind) {
        case "session": {
          if (
            v.kind === "profile" &&
            v.profile === ev.profile &&
            v.sessionId === ev.session_id &&
            !pendingTurnRef.current
          ) {
            scheduleSessionRefresh(ev.profile, ev.session_id);
          }
          scheduleReload();
          break;
        }
        case "workgroup_transcript": {
          const key = `${ev.profile}/${ev.wg_id}`;
          setActivityByWorkgroup((prev) => ({ ...prev, [key]: Date.now() }));
          scheduleReload(250);
          invoke("workgroup_transcript", {
            profile: ev.profile,
            wgId: ev.wg_id,
          })
            .then((msgs) => {
              if (!Array.isArray(msgs)) return;
              const hub =
                profilesRef.current.find((p) => p.name === ev.profile)
                  ?.pubkey_b64 ?? null;
              const task = findLatestTask(msgs, hub);
              setTaskByWorkgroup((prev) => {
                if (task == null) return prev;
                return prev[key] === task ? prev : { ...prev, [key]: task };
              });
              seenMtimesRef.current = {
                ...seenMtimesRef.current,
                [key]: Math.floor(Date.now() / 1000),
              };
              saveCachedMessages(ev.profile, ev.wg_id, msgs);
            })
            .catch(() => {});
          break;
        }
        case "workgroup_meta":
        case "workgroup_members":
        case "peers":
        case "subscriptions":
        case "config":
          scheduleReload();
          break;
        default:
          break;
      }
    });
    return () => {
      off.then((fn) => fn());
    };
  }, [scheduleReload, scheduleSessionRefresh]);

  // Buffer streaming deltas so token chunks do not render markdown on every frame.
  const deltaBufferRef = useRef({ assistant: "", reasoning: "" });
  const deltaFlushScheduledRef = useRef(false);
  const flushDeltas = useCallback(() => {
    deltaFlushScheduledRef.current = false;
    const { assistant, reasoning } = deltaBufferRef.current;
    if (!assistant && !reasoning) return;
    deltaBufferRef.current = { assistant: "", reasoning: "" };
    setPendingTurn((prev) => {
      if (!prev) return prev;
      const next = { ...prev };
      if (assistant)
        next.assistantPreview = (prev.assistantPreview ?? "") + assistant;
      if (reasoning)
        next.reasoningPreview = (prev.reasoningPreview ?? "") + reasoning;
      return next;
    });
  }, []);
  const deltaFlushTimerRef = useRef(null);
  const scheduleDeltaFlush = useCallback(() => {
    if (deltaFlushScheduledRef.current) return;
    deltaFlushScheduledRef.current = true;
    deltaFlushTimerRef.current = setTimeout(flushDeltas, 50);
  }, [flushDeltas]);

  useEffect(() => {
    return () => {
      if (deltaFlushTimerRef.current) clearTimeout(deltaFlushTimerRef.current);
    };
  }, []);

  useEffect(() => {
    const off = listen("chat-event", (event) => {
      const p = event.payload;
      if (p.kind === "tool_start") {
        setPendingTurn((prev) =>
          prev
            ? {
                ...prev,
                tools: [
                  ...prev.tools,
                  {
                    tool_id: p.tool_id,
                    name: p.name,
                    preview: p.preview,
                    args: p.args,
                    states: [],
                    output: "",
                    ok: null,
                    startedAt: Date.now(),
                  },
                ],
              }
            : prev,
        );
      } else if (p.kind === "tool_state") {
        setPendingTurn((prev) => {
          if (!prev) return prev;
          const tools = prev.tools.map((t) =>
            t.tool_id === p.tool_id && t.ok === null
              ? { ...t, states: [...t.states, { text: p.text, ok: p.ok }] }
              : t,
          );
          return { ...prev, tools };
        });
      } else if (p.kind === "tool_end") {
        const MIN_RUNNING_MS = 280;
        const matchTool = (t) =>
          (p.tool_id && t.tool_id === p.tool_id) ||
          (!p.tool_id && t.name === p.name && t.ok === null);
        function applyEnd() {
          setPendingTurn((prev) => {
            if (!prev) return prev;
            const tools = [...prev.tools];
            for (let i = tools.length - 1; i >= 0; i--) {
              if (matchTool(tools[i])) {
                tools[i] = {
                  ...tools[i],
                  ok: p.ok,
                  output: p.output ?? "",
                };
                break;
              }
            }
            return { ...prev, tools };
          });
        }
        setPendingTurn((prev) => {
          if (!prev) return prev;
          let idx = -1;
          for (let i = prev.tools.length - 1; i >= 0; i--) {
            if (matchTool(prev.tools[i])) {
              idx = i;
              break;
            }
          }
          if (idx === -1) return prev;
          const startedAt = prev.tools[idx].startedAt ?? Date.now();
          const elapsed = Date.now() - startedAt;
          if (elapsed >= MIN_RUNNING_MS) {
            const tools = [...prev.tools];
            tools[idx] = {
              ...tools[idx],
              ok: p.ok,
              output: p.output ?? "",
            };
            return { ...prev, tools };
          }
          setTimeout(applyEnd, MIN_RUNNING_MS - elapsed);
          return prev;
        });
      } else if (p.kind === "assistant_delta") {
        deltaBufferRef.current.assistant += p.text;
        scheduleDeltaFlush();
      } else if (p.kind === "reasoning_delta") {
        deltaBufferRef.current.reasoning += p.text;
        scheduleDeltaFlush();
      } else if (p.kind === "error") {
        setPendingTurn((prev) =>
          prev ? { ...prev, error: p.text } : prev,
        );
      } else if (p.kind === "reply") {
        setPendingTurn((prev) => {
          if (!prev || !p.session_id) return prev;
          const profileName = prev.profile;
          invoke("session_detail", {
            profile: profileName,
            id: p.session_id,
          })
            .then((newData) => {
              setSessionData(newData);
              setRewriteDraft(null);
              setView({
                kind: "profile",
                profile: profileName,
                sessionId: p.session_id,
              });
              reloadRef.current?.();
            })
            .catch((e) => setError(String(e)));
          return prev;
        });
      } else if (p.kind === "done") {
        // Drop any buffered deltas — the persisted session already has them.
        deltaBufferRef.current = { assistant: "", reasoning: "" };
        setPendingTurn((prev) => (prev?.error ? prev : null));
      }
    });
    return () => {
      off.then((fn) => fn());
    };
  }, []);

  const sendingRef = useRef(false);
  const onSend = useCallback(
    async (text, model) => {
      if (!text.trim() || !activeProfile) return;
      if (sendingRef.current) return;
      sendingRef.current = true;
      try {
        const profileName = activeProfile.name;
        const startSessionId =
          view.kind === "profile" ? view.sessionId : null;
        const rewriteFromTurn =
          rewriteDraft &&
          rewriteDraft.profile === profileName &&
          rewriteDraft.sessionId === startSessionId
            ? rewriteDraft.turnIndex
            : null;

        if (pendingTurn && pendingTurn.profile === profileName) {
          try {
            await invoke("chat_cancel", { profile: profileName });
          } catch {}
        }

        setPendingTurn({
          user: text,
          tools: [],
          error: null,
          profile: profileName,
          sessionId: startSessionId,
        });

        try {
          await invoke("chat_send_stream", {
            profile: profileName,
            sessionId: startSessionId,
            rewriteFromTurn,
            text,
            model: model ?? null,
          });
        } catch (e) {
          setError(String(e));
          setPendingTurn(null);
        }
      } finally {
        sendingRef.current = false;
      }
    },
    [activeProfile, view, pendingTurn, rewriteDraft],
  );

  const activeWorkgroup = useMemo(() => {
    if (view.kind === "workgroup") {
      return (
        workgroups.find(
          (w) => w.id === view.id && w.profile === view.profile,
        ) ?? null
      );
    }
    return null;
  }, [view, workgroups]);

  return (
    <div className={styles.app} data-sidebar-collapsed={collapsed ? "1" : "0"}>
      <AppHeader
        view={view}
        collapsed={view.kind === "settings" ? true : collapsed}
        profiles={profiles}
        activeProfile={activeProfile}
        activeWorkgroup={activeWorkgroup}
        settingsWorkgroup={activeSettingsWorkgroup}
        activeTask={activeTask}
        sessionData={sessionData}
        onToggleSidebar={toggleSidebar}
        onChangeSession={onChangeSession}
        onNewSession={onNewSessionForCurrentProfile}
        onCloseSettings={closeSettings}
      />
      <div className={styles.shell}>
        {view.kind !== "settings" && (
          <Sidebar
            collapsed={collapsed}
            profiles={profiles}
            workgroups={workgroups}
            taskByWorkgroup={taskByWorkgroup}
            activityByWorkgroup={activityByWorkgroup}
            pendingProfile={pendingTurn?.profile ?? null}
            view={view}
            pinned={pinned}
            hostConnections={hostConnections}
            onNewChat={onNewChat}
            onOpenProfile={onOpenProfile}
            onOpenWorkgroup={onOpenWorkgroup}
            onTogglePin={onTogglePin}
            onSetHostConnection={onSetHostConnection}
            onAddHostConnection={onAddHostConnection}
            onForgetHostConnection={onForgetHostConnection}
            onRefreshHostConnectionStatus={onRefreshHostConnectionStatus}
          />
        )}
        <main className={styles.main}>
          {error && <div className={styles.error}>{error}</div>}
          {view.kind === "settings" && (
            <Settings
              profiles={profiles}
              workgroups={workgroups}
              target={settingsTarget}
              hostConnections={hostConnections}
              onSelectTarget={setSettingsTarget}
              onRefresh={reload}
              onSetHostConnection={onSetHostConnection}
              onAddHostConnection={onAddHostConnection}
              onForgetHostConnection={onForgetHostConnection}
              onRefreshHostConnectionStatus={onRefreshHostConnectionStatus}
            />
          )}
          {view.kind === "workgroup" && activeWorkgroup && (
            <WorkgroupView
              key={`${activeWorkgroup.profile}/${activeWorkgroup.id}`}
              workgroup={activeWorkgroup}
              profiles={profiles}
              onActiveTask={(task) => {
                setActiveTask(task);
                if (task == null) return;
                const key = `${activeWorkgroup.profile}/${activeWorkgroup.id}`;
                setTaskByWorkgroup((prev) =>
                  prev[key] === task ? prev : { ...prev, [key]: task },
                );
              }}
            />
          )}
          {(view.kind === "empty" || view.kind === "profile") && (
          <ChatPane
              view={view}
              profiles={profiles}
              activeProfile={activeProfile}
              sessionData={sessionData}
              pendingTurn={
                pendingTurn && pendingTurn.profile === activeProfile?.name
                  ? pendingTurn
                  : null
              }
              onSend={onSend}
              onSelectProfile={(name) => {
                setPickerAlpi(name);
                if (view.kind === "profile") {
                  const p = profiles.find((x) => x.name === name);
                  if (p) onOpenProfile(p);
                }
              }}
              onRewriteMessage={onRewriteMessage}
              rewriteDraft={rewriteDraft}
              onRewriteDraftApplied={() => {
                setRewriteDraft((prev) => (prev ? { ...prev, consumed: true } : prev));
              }}
            />
          )}
        </main>
      </div>
    </div>
  );
}
