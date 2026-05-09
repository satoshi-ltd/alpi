import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import AppHeader from "./components/AppHeader.jsx";
import Sidebar from "./components/Sidebar.jsx";
import ChatPane from "./components/ChatPane.jsx";
import OfflineBanner from "./components/OfflineBanner.jsx";
import WorkgroupView from "./components/WorkgroupView.jsx";
import Settings from "./components/Settings.jsx";
import { useNotify } from "./primitives/Notification.jsx";
import { installUpdater } from "./lib/updater.js";
import { findLatestTask } from "./lib/workgroup-tasks.js";
import { saveCachedMessages } from "./lib/workgroup-cache.js";
import { useChatStream } from "./hooks/useChatStream.js";
import { useHostConnections } from "./hooks/useHostConnections.js";
import { useNavListener } from "./hooks/useNavListener.js";
import { usePinned } from "./hooks/usePinned.js";
import { useWindowChrome } from "./hooks/useWindowChrome.js";
import { useWorkgroupTasks } from "./hooks/useWorkgroupTasks.js";
import styles from "./App.module.css";

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

export default function App() {
  const notify = useNotify();
  const [view, setView] = useState({ kind: "empty" });
  const [settingsTarget, setSettingsTarget] = useState({
    kind: "profile",
    id: null,
  });
  const [sessionData, setSessionData] = useState(null);
  const [rewriteDraft, setRewriteDraft] = useState(null);
  const [activeTask, setActiveTask] = useState(null);

  const viewRef = useRef(view);
  const prevViewRef = useRef(view);
  useEffect(() => {
    if (view.kind !== "settings") prevViewRef.current = view;
    viewRef.current = view;
  }, [view]);

  const reloadRef = useRef(null);
  const pendingTurnRef = useRef(null);

  const { collapsed, setCollapsed, toggleSidebar } = useWindowChrome({
    viewRef,
    setView,
  });
  useNavListener(setView);
  const { pinned, onTogglePin } = usePinned();

  const { pendingTurn, setPendingTurn } = useChatStream({
    setSessionData,
    setView,
    setRewriteDraft,
    reloadRef,
    notify,
  });
  useEffect(() => {
    pendingTurnRef.current = pendingTurn;
  }, [pendingTurn]);

  const {
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
  } = useHostConnections({
    setSessionData,
    setPendingTurn,
    setRewriteDraft,
    setActiveTask,
    setView,
    pendingTurnRef,
  });

  useEffect(() => {
    reloadRef.current = reload;
  }, [reload]);

  const profilesRef = useRef(profiles);
  useEffect(() => {
    profilesRef.current = profiles;
  }, [profiles]);

  const hubPubkeyOf = useCallback(
    (profileName) =>
      profiles.find((p) => p.name === profileName)?.pubkey_b64 ?? null,
    [profiles],
  );

  const {
    taskByWorkgroup,
    setTaskByWorkgroup,
    activityByWorkgroup,
    setActivityByWorkgroup,
    seenMtimesRef,
  } = useWorkgroupTasks({ workgroups, hubPubkeyOf });

  const [settingsRefreshTick, setSettingsRefreshTick] = useState(0);
  const [settingsRefreshing, setSettingsRefreshing] = useState(false);
  const onSettingsRefresh = useCallback(async () => {
    setSettingsRefreshing(true);
    try {
      await reload();
    } finally {
      setSettingsRefreshTick((t) => t + 1);
      setSettingsRefreshing(false);
    }
  }, [reload]);

  useEffect(() => installUpdater(), []);

  // Load session detail when the active session changes.
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

  // React to filesystem-level changes the daemon broadcasts.
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
  }, [
    scheduleReload,
    scheduleSessionRefresh,
    setActivityByWorkgroup,
    setTaskByWorkgroup,
    seenMtimesRef,
  ]);

  const sendingRef = useRef(false);
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
          notify({ message: String(e), variant: "error" });
          setPendingTurn(null);
        }
      } finally {
        sendingRef.current = false;
      }
    },
    [activeProfile, view, pendingTurn, rewriteDraft, notify, setPendingTurn],
  );

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

  const closeSettings = useCallback(() => {
    setView(
      prevViewRef.current && prevViewRef.current.kind !== "settings"
        ? prevViewRef.current
        : { kind: "empty" },
    );
  }, []);

  const activeSettingsWorkgroup = useMemo(() => {
    if (view.kind !== "settings" || settingsTarget.kind !== "workgroup") {
      return null;
    }
    return workgroups.find((w) => w.id === settingsTarget.id) ?? null;
  }, [view, settingsTarget, workgroups]);

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

  const activeConnection = hostConnections.connections.find(
    (c) => c.id === hostConnections.active_id,
  );
  const daemonOffline =
    !!activeConnection &&
    (activeConnection.status === "offline" ||
      activeConnection.status === "auth-failed");

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
        settingsRefreshing={settingsRefreshing}
        onToggleSidebar={toggleSidebar}
        onChangeSession={onChangeSession}
        onNewSession={onNewSessionForCurrentProfile}
        onCloseSettings={closeSettings}
        onSettingsRefresh={onSettingsRefresh}
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
            daemonOffline={daemonOffline}
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
          {view.kind === "settings" ? (
            <Settings
              profiles={profiles}
              workgroups={workgroups}
              target={settingsTarget}
              hostConnections={hostConnections}
              activeConnection={activeConnection}
              refreshTick={settingsRefreshTick}
              onSelectTarget={setSettingsTarget}
              onRefresh={reload}
              onSetHostConnection={onSetHostConnection}
              onAddHostConnection={onAddHostConnection}
              onForgetHostConnection={onForgetHostConnection}
              onRefreshHostConnectionStatus={onRefreshHostConnectionStatus}
            />
          ) : daemonOffline ? (
            <OfflineBanner
              connectionName={activeConnection?.name}
              connectionDetail={
                activeConnection?.kind === "remote"
                  ? `${activeConnection.host}:${activeConnection.port}`
                  : activeConnection ? "host.sock" : undefined
              }
              onRetry={onRefreshHostConnectionStatus}
            />
          ) : (
            <>
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
                    setRewriteDraft((prev) =>
                      prev ? { ...prev, consumed: true } : prev,
                    );
                  }}
                />
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
