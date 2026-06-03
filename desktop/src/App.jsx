import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { safeUnlisten } from "./lib/tauri-listen.js";
import Sidebar from "./features/Sidebar.jsx";
import ChatPane from "./pages/ChatPane.jsx";
import WorkgroupView from "./pages/WorkgroupView.jsx";
import Settings from "./pages/Settings.jsx";
import { Banner } from "./primitives/index.js";
import { useNotify } from "./primitives/Notification.jsx";
import CommandPalette from "./features/CommandPalette.jsx";
import ApprovalModal from "./features/ApprovalModal.jsx";
import ClarificationModal from "./features/ClarificationModal.jsx";
import CreateProfileModal from "./features/CreateProfileModal.jsx";
import CreateWorkgroupModal from "./features/CreateWorkgroupModal.jsx";
import NotificationsModal from "./features/NotificationsModal.jsx";
import ToolsPanel from "./features/ToolsPanel.jsx";
import SkillsPanel from "./features/SkillsPanel.jsx";
import MemoryPanel from "./features/MemoryPanel.jsx";
import { useCommands } from "./hooks/useCommands.js";
import { orderedJumpTargets } from "./lib/profile-order.js";
import { installUpdater } from "./lib/updater.js";
import { findLatestTask } from "./lib/workgroup-tasks.js";
import { saveCachedMessages } from "./lib/workgroup-cache.js";
import { fetchWorkgroupTranscript, invalidateTranscriptCache } from "./lib/workgroup-fetch.js";
import { fromDaemonFrame } from "./lib/daemon-frame.js";
import { enqueueRequest as enqueueApprovalRequest } from "./lib/approval-queue.js";
import { enqueueRequest as enqueueClarificationRequest } from "./lib/clarification-queue.js";
import { invalidateProfileDetailCache } from "./hooks/useProfileDetail.js";
import { useChatStream } from "./hooks/useChatStream.js";
import { useHostConnections } from "./hooks/useHostConnections.js";
import { useOutputs } from "./hooks/useOutputs.js";
import { useNavListener } from "./hooks/useNavListener.js";
import { usePinned } from "./hooks/usePinned.js";
import { useLastView } from "./hooks/useLastView.js";
import { useActiveRole } from "./hooks/useActiveRole.js";
import { useWorkgroupTasks } from "./hooks/useWorkgroupTasks.js";
import { markWorkgroupRead } from "./hooks/useReadState.js";
import { useWindowChrome } from "./hooks/useWindowChrome.js";
import {
  useActiveViewPing,
  useNotificationDeeplink,
} from "./hooks/useNotificationDeeplink.js";
import { useDaemonAutostart } from "./hooks/useDaemonAutostart.js";
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
  const [recents, setRecents] = useState([]);

  const viewRef = useRef(view);
  const prevViewRef = useRef(view);
  useEffect(() => {
    if (view.kind !== "settings") prevViewRef.current = view;
    viewRef.current = view;
  }, [view]);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notificationsTarget, setNotificationsTarget] = useState(null);
  const openNotificationsForDeeplink = useCallback((target) => {
    setNotificationsTarget(target || null);
    setNotificationsOpen(true);
  }, []);
  const onOpenNotifications = useCallback(() => {
    setNotificationsTarget(null);
    setNotificationsOpen((v) => !v);
  }, []);
  const onCloseNotifications = useCallback(() => {
    setNotificationsOpen(false);
    setNotificationsTarget(null);
  }, []);
  useNotificationDeeplink({
    setView,
    setSettingsTarget,
    openNotifications: openNotificationsForDeeplink,
  });
  useActiveViewPing(view);

  const onOpenRecent = useCallback((profile, sessionId) => {
    setView({ kind: "profile", profile, sessionId });
  }, []);

  useEffect(() => {
    const onTtsError = (ev) => {
      const err = ev.detail?.error || "audio failed";
      notify({ message: `Audio: ${err}`, variant: "error" });
    };
    window.addEventListener("alpi-tts-error", onTtsError);
    return () => window.removeEventListener("alpi-tts-error", onTtsError);
  }, [notify]);

  const settingsTargetRef = useRef(settingsTarget);
  useEffect(() => {
    settingsTargetRef.current = settingsTarget;
  }, [settingsTarget]);
  const workgroupsRef = useRef([]);

  const reloadRef = useRef(null);
  const pendingTurnRef = useRef(null);

  const jumpTargetsRef = useRef([]);
  const onJumpToProfile = useCallback((index) => {
    const item = jumpTargetsRef.current[index];
    if (!item) return;
    if (viewRef.current?.kind === "settings") {
      if (item.kind === "profile") {
        setSettingsTarget({ kind: "profile", id: item.target.name });
      } else if (item.kind === "workgroup") {
        setSettingsTarget({ kind: "workgroup", id: item.target.id });
      }
      return;
    }
    if (item.kind === "profile") {
      setRewriteDraft(null);
      setView({
        kind: "profile",
        profile: item.target.name,
        sessionId:
          item.target.latest_session && item.target.latest_session.kind === "chat"
            ? item.target.latest_session.id
            : null,
      });
    } else if (item.kind === "workgroup") {
      setView({
        kind: "workgroup",
        profile: item.target.profile,
        id: item.target.id,
      });
    }
  }, []);
  const activeRole = useActiveRole();
  // Pre-probe (``null``) defaults to allow — local Unix socket users have no token but are admin-equiv, and the role probe lands within a couple seconds for remote.
  const canAdminEarly = activeRole === "admin" || activeRole == null;
  const [createProfileOpen, setCreateProfileOpen] = useState(false);
  const onNewProfile = useCallback(() => {
    setCreateProfileOpen(true);
  }, []);
  const [createWorkgroupOpen, setCreateWorkgroupOpen] = useState(false);
  const onNewWorkgroup = useCallback(() => {
    setCreateWorkgroupOpen(true);
  }, []);
  const adminOnNewProfile = canAdminEarly ? onNewProfile : null;
  const adminOnNewWorkgroup = canAdminEarly ? onNewWorkgroup : null;
  const [searchOpen, setSearchOpen] = useState(false);
  const searchOpenRef = useRef(false);
  useEffect(() => {
    searchOpenRef.current = searchOpen;
  }, [searchOpen]);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const paletteOpenRef = useRef(false);
  useEffect(() => {
    paletteOpenRef.current = paletteOpen;
  }, [paletteOpen]);
  const onTogglePalette = useCallback(() => {
    setPaletteOpen((v) => !v);
  }, []);
  const onClosePalette = useCallback(() => setPaletteOpen(false), []);

  const [approvalQueue, setApprovalQueue] = useState([]);
  const onApprovalResolved = useCallback((requestId) => {
    setApprovalQueue((q) => q.filter((r) => r.request_id !== requestId));
  }, []);
  const mergeApprovalRequest = useCallback((req) => {
    setApprovalQueue((q) => enqueueApprovalRequest(q, req));
  }, []);

  const [clarificationQueue, setClarificationQueue] = useState([]);
  const onClarificationResolved = useCallback((requestId) => {
    setClarificationQueue((q) => q.filter((r) => r.request_id !== requestId));
  }, []);
  const mergeClarificationRequest = useCallback((req) => {
    setClarificationQueue((q) => enqueueClarificationRequest(q, req));
  }, []);

  const [browse, setBrowse] = useState(null);
  const onCloseBrowse = useCallback(() => setBrowse(null), []);
  const onBrowseTools = useCallback(() => setBrowse("tools"), []);
  const onBrowseSkills = useCallback(() => setBrowse("skills"), []);
  const onBrowseMemory = useCallback(() => setBrowse("memory"), []);
  const onToggleSearch = useCallback(() => {
    if (searchOpenRef.current) {
      setSearchOpen(false);
      return;
    }
    const v = viewRef.current;
    if (v?.kind === "profile" || v?.kind === "workgroup") {
      setSearchOpen(true);
    }
  }, []);
  const onCloseSearch = useCallback(() => setSearchOpen(false), []);
  useEffect(() => {
    setSearchOpen(false);
  }, [view.kind, view.profile, view.sessionId, view.id]);
  // Member devices have no Settings surface — snap back to empty if state ever points there (deeplink, nav event, ⌘, race).
  useEffect(() => {
    if (!canAdminEarly && view.kind === "settings") {
      setView({ kind: "empty" });
    }
  }, [canAdminEarly, view.kind]);
  const onOpenSettings = useCallback(() => {
    const v = viewRef.current;
    if (v?.kind === "settings") {
      const t = settingsTargetRef.current;
      if (t?.kind === "profile" && t.id) {
        const profile = profilesRef.current.find((p) => p.name === t.id);
        const latest = profile?.latest_session;
        setView({
          kind: "profile",
          profile: t.id,
          sessionId: latest?.kind === "chat" ? latest.id : null,
        });
        return;
      }
      if (t?.kind === "workgroup" && t.id) {
        const wg = workgroupsRef.current.find((w) => w.id === t.id);
        if (wg) {
          setView({ kind: "workgroup", profile: wg.profile, id: wg.id });
          return;
        }
      }
      setView(
        prevViewRef.current && prevViewRef.current.kind !== "settings"
          ? prevViewRef.current
          : { kind: "empty" },
      );
      return;
    }
    if (v?.kind === "profile") {
      setSettingsTarget({ kind: "profile", id: v.profile });
    } else if (v?.kind === "workgroup") {
      setSettingsTarget({ kind: "workgroup", id: v.id });
    }
    setView({ kind: "settings" });
  }, []);
  const adminOnOpenSettings = canAdminEarly ? onOpenSettings : null;
  useWindowChrome({
    viewRef,
    setView,
    onJumpToProfile,
    onNewProfile: adminOnNewProfile,
    onNewWorkgroup: adminOnNewWorkgroup,
    onOpenSettings: adminOnOpenSettings,
    onToggleSearch,
    onTogglePalette,
    paletteOpenRef,
    onClosePalette,
    onBrowseTools,
    onBrowseSkills,
    onBrowseMemory,
    onToggleNotifications: onOpenNotifications,
  });
  useNavListener(setView);

  const { pendingTurn, setPendingTurn, activeRequestIdRef } = useChatStream({
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

  const { rows: unreadOutputs } = useOutputs({
    profiles,
    connectionId: hostConnections.active_id,
    status: "unread",
  });
  const notificationsUnread = unreadOutputs.length;

  useEffect(() => {
    invoke("tray_announce_notifications", { unread: notificationsUnread }).catch(() => {});
  }, [notificationsUnread]);

  useEffect(() => {
    let cancelled = false;
    let unlisten = null;
    listen("tray:notifications-clicked", () => {
      setNotificationsTarget(null);
      setNotificationsOpen(true);
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

  const { pinned, onTogglePin } = usePinned(hostConnections.active_id);
  useLastView({
    connectionId: hostConnections.active_id,
    view,
    setView,
    profiles,
    workgroups,
  });

  // On connection switch drop cache for BOTH prev and new active: events from the new daemon weren't received while we were elsewhere, so anything still cached for it is potentially stale.
  const prevConnectionIdRef = useRef(hostConnections.active_id);
  useEffect(() => {
    const prev = prevConnectionIdRef.current;
    if (prev !== hostConnections.active_id) {
      if (prev) {
        invalidateTranscriptCache(prev);
        invalidateProfileDetailCache(prev);
      }
      invalidateTranscriptCache(hostConnections.active_id);
      invalidateProfileDetailCache(hostConnections.active_id);
    }
    prevConnectionIdRef.current = hostConnections.active_id;
  }, [hostConnections.active_id]);

  useEffect(() => {
    if (view.kind !== "empty") return;
    setRecents([]);
    let cancelled = false;
    invoke("sessions", { limit: 8 })
      .then((rows) => {
        if (cancelled) return;
        const list = Array.isArray(rows) ? rows : [];
        const sorted = list
          .filter((s) => s.kind === "chat" && s.first_user)
          .sort((a, b) => (b.updated_at || b.mtime || 0) - (a.updated_at || a.mtime || 0))
          .slice(0, 4);
        setRecents(sorted);
      })
      .catch(() => { if (!cancelled) setRecents([]); });
    return () => { cancelled = true; };
  }, [view.kind, hostConnections.active_id]);

  const profilesRef = useRef(profiles);
  useEffect(() => {
    profilesRef.current = profiles;
  }, [profiles]);
  useEffect(() => {
    workgroupsRef.current = workgroups;
  }, [workgroups]);

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
  } = useWorkgroupTasks({ workgroups, hubPubkeyOf, connectionId: hostConnections.active_id });

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

  const onRefreshSession = useCallback(() => {
    const v = viewRef.current;
    if (v?.kind === "profile" && v.profile && v.sessionId) {
      invoke("session_detail", { profile: v.profile, id: v.sessionId })
        .then((data) => {
          if (isChatSessionData(data)) setSessionData(data);
        })
        .catch(() => {});
    }
    reloadRef.current?.();
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

  // Same reducer for fs-change (local watcher) and daemon-event (works on remote too).
  const applyChange = useCallback((ev) => {
    if (!ev || !ev.kind) return;
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
        const connectionId = hostConnectionsRef.current?.active_id;
        setActivityByWorkgroup((prev) => ({ ...prev, [key]: Date.now() }));
        scheduleReload(250);
        fetchWorkgroupTranscript(connectionId, ev.profile, ev.wg_id)
          .then((msgs) => {
            if (!Array.isArray(msgs)) return;
            // Drop late result from a previous daemon.
            if (hostConnectionsRef.current?.active_id !== connectionId) return;
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
            saveCachedMessages(connectionId, ev.profile, ev.wg_id, msgs);
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
  }, [scheduleReload, scheduleSessionRefresh, setActivityByWorkgroup, setTaskByWorkgroup, seenMtimesRef]);

  // fromDaemonFrame lives in lib/daemon-frame.js (pure, unit-tested).

  useEffect(() => {
    let cancelled = false;
    let unlistenFs = null;
    let unlistenDaemon = null;
    listen("fs-change", (e) => applyChange(e.payload))
      .then((fn) => {
        if (cancelled) safeUnlisten(fn);
        else unlistenFs = fn;
      })
      .catch(() => {});
    listen("daemon-event", (e) => {
      const payload = e.payload ?? {};
      // Drop frames from a non-active daemon.
      if (
        payload.connection_id &&
        payload.connection_id !== hostConnectionsRef.current?.active_id
      ) {
        return;
      }
      const frame = payload.frame ?? payload;
      // approval.request: enqueue caution prompt. approval.resolved: pop in case another client answered first.
      if (frame?.event === "approval.request") {
        mergeApprovalRequest(frame.data ?? {});
        return;
      }
      if (frame?.event === "approval.resolved") {
        const rid = frame.data?.request_id;
        if (rid) setApprovalQueue((q) => q.filter((r) => r.request_id !== rid));
        return;
      }
      if (frame?.event === "clarification.request") {
        mergeClarificationRequest(frame.data ?? {});
        return;
      }
      if (frame?.event === "clarification.resolved") {
        const rid = frame.data?.request_id;
        if (rid) setClarificationQueue((q) => q.filter((r) => r.request_id !== rid));
        return;
      }
      const mapped = fromDaemonFrame(frame);
      if (mapped) applyChange(mapped);
    })
      .then((fn) => {
        if (cancelled) safeUnlisten(fn);
        else unlistenDaemon = fn;
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      safeUnlisten(unlistenFs);
      safeUnlisten(unlistenDaemon);
    };
  }, [applyChange, hostConnectionsRef, mergeApprovalRequest, mergeClarificationRequest]);

  // Cold-start recovery: subscribe anchors at next_seq so requests emitted before mount won't reach the stream. Fetch pending now and after any connection switch.
  // ALSO drop the previous connection's queue: a stale entry would route host.approval.respond through the NEW daemon and either return unknown or, worse, confuse the user.
  useEffect(() => {
    setApprovalQueue([]);
    let cancelled = false;
    invoke("approval_pending")
      .then((res) => {
        if (cancelled) return;
        const items = res?.requests || [];
        for (const it of items) mergeApprovalRequest(it);
      })
      .catch(() => { /* daemon may be offline / older */ });
    return () => { cancelled = true; };
  }, [hostConnections.active_id, mergeApprovalRequest]);

  useEffect(() => {
    setClarificationQueue([]);
    let cancelled = false;
    invoke("clarification_pending")
      .then((res) => {
        if (cancelled) return;
        const items = res?.requests || [];
        for (const it of items) mergeClarificationRequest(it);
      })
      .catch(() => { /* daemon may be offline / older */ });
    return () => { cancelled = true; };
  }, [hostConnections.active_id, mergeClarificationRequest]);

  const sendingRef = useRef(false);
  const activeProfile = useMemo(() => {
    if (view.kind === "profile") {
      return profiles.find((p) => p.name === view.profile) ?? null;
    }
    if (view.kind === "settings" && settingsTarget?.kind === "profile") {
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
    async (text, model, opts) => {
      if (!text.trim() || !activeProfile) return;
      if (sendingRef.current) return;
      sendingRef.current = true;
      try {
        const profileName = activeProfile.name;
        const startSessionId =
          view.kind === "profile" ? view.sessionId : null;
        const overrideTurn =
          opts && Number.isInteger(opts.rewriteFromTurn)
            ? opts.rewriteFromTurn
            : null;
        const rewriteFromTurn = overrideTurn ?? (
          rewriteDraft &&
          rewriteDraft.profile === profileName &&
          rewriteDraft.sessionId === startSessionId
            ? rewriteDraft.turnIndex
            : null
        );

        if (pendingTurn && pendingTurn.profile === profileName) {
          try {
            await invoke("chat_cancel", { profile: profileName });
          } catch {}
        }

        const requestId = `desktop-${profileName}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        activeRequestIdRef.current = requestId;

        setPendingTurn({
          user: text,
          tools: [],
          error: null,
          profile: profileName,
          sessionId: startSessionId,
          requestId,
        });

        try {
          await invoke("chat_send_stream", {
            profile: profileName,
            sessionId: startSessionId,
            rewriteFromTurn,
            text,
            model: model ?? null,
            requestId,
          });
        } catch (e) {
          notify({ message: String(e), variant: "error" });
          setPendingTurn(null);
        }
      } finally {
        sendingRef.current = false;
      }
    },
    [activeProfile, view, pendingTurn, rewriteDraft, notify, setPendingTurn, activeRequestIdRef],
  );

  const onCancelTurn = useCallback(() => {
    const pending = pendingTurnRef.current;
    if (!pending?.profile) return;
    invoke("chat_cancel", { profile: pending.profile }).catch(() => {});
  }, []);

  useEffect(() => {
    function onKey(e) {
      if (e.key !== "Escape") return;
      if (e.defaultPrevented) return;
      if (!pendingTurnRef.current?.profile) return;
      e.preventDefault();
      onCancelTurn();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onCancelTurn]);

  const onNewChat = useCallback(() => {
    setRewriteDraft(null);
    setView({ kind: "empty" });
  }, []);

  const onSelectWorkgroup = useCallback((wg) => {
    setView({ kind: "workgroup", profile: wg.profile, id: wg.id });
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

  const onRetryMessage = useCallback((profileName, sessionId, turnIndex, text) => {
    if (!profileName || !sessionId || !text) return;
    onSend(text, null, { rewriteFromTurn: turnIndex });
  }, [onSend]);

  const onOpenWorkgroup = useCallback((workgroup) => {
    setView({
      kind: "workgroup",
      profile: workgroup.profile,
      id: workgroup.id,
    });
  }, []);

  const closeSettings = useCallback(() => {
    const t = settingsTargetRef.current;
    if (t?.kind === "profile" && t.id) {
      const profile = profilesRef.current.find((p) => p.name === t.id);
      const latest = profile?.latest_session;
      setView({
        kind: "profile",
        profile: t.id,
        sessionId: latest?.kind === "chat" ? latest.id : null,
      });
      return;
    }
    if (t?.kind === "workgroup" && t.id) {
      const wg = workgroupsRef.current.find((w) => w.id === t.id);
      if (wg) {
        setView({ kind: "workgroup", profile: wg.profile, id: wg.id });
        return;
      }
    }
    setView(
      prevViewRef.current && prevViewRef.current.kind !== "settings"
        ? prevViewRef.current
        : { kind: "empty" },
    );
  }, []);

  const activeSettingsWorkgroup = useMemo(() => {
    if (view.kind !== "settings" || settingsTarget?.kind !== "workgroup") {
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

  const [autostartPhase, setAutostartPhase] = useState("idle");
  useDaemonAutostart({ activeConnection, onAttempt: setAutostartPhase });

  const activeStatus = activeConnection?.status;
  const isLocalAutostartInFlight =
    activeConnection?.kind === "local" &&
    activeStatus === "offline" &&
    autostartPhase === "starting";

  // Local connections defer to autostart; only auto-open after it gave up.
  const autoOpenConnectionSwitcher =
    hostConnections.connections.length > 0 &&
    (activeStatus === "auth-failed" ||
      (activeStatus === "offline" &&
        (activeConnection?.kind !== "local" || autostartPhase === "gave-up")));

  const jumpTargets = useMemo(
    () =>
      orderedJumpTargets({
        profiles,
        workgroups,
        pinnedProfiles: pinned.profiles ?? [],
        pinnedWorkgroups: pinned.workgroups ?? [],
      }),
    [profiles, workgroups, pinned],
  );

  useEffect(() => {
    jumpTargetsRef.current = jumpTargets;
  }, [jumpTargets]);

  const jumpHints = useMemo(() => {
    const out = {};
    jumpTargets.slice(0, 9).forEach((item, i) => {
      const k =
        item.kind === "profile"
          ? `profile:${item.target.name}`
          : `workgroup:${item.target.profile}/${item.target.id}`;
      out[k] = i + 1;
    });
    return out;
  }, [jumpTargets]);

  const paletteCommands = useCommands({
    view,
    profiles,
    workgroups,
    pinned,
    searchOpen,
    onSelectProfile: onOpenProfile,
    onSelectWorkgroup,
    onOpenSettings: adminOnOpenSettings,
    onCloseSettings: closeSettings,
    onToggleSearch,
    onNewProfile: adminOnNewProfile,
    onNewWorkgroup: adminOnNewWorkgroup,
    onNewChat,
    onBrowseTools,
    onBrowseSkills,
    onBrowseMemory,
  });

  return (
    <div className={styles.app}>
      <Sidebar
        profiles={profiles}
        workgroups={workgroups}
        taskByWorkgroup={taskByWorkgroup}
        activityByWorkgroup={activityByWorkgroup}
        pendingProfile={pendingTurn?.profile ?? null}
        view={view}
        settingsTarget={settingsTarget}
        pinned={pinned}
        jumpHints={jumpHints}
        hostConnections={hostConnections}
        daemonOffline={daemonOffline}
        onNewChat={onNewChat}
        onOpenProfile={onOpenProfile}
        onOpenWorkgroup={onOpenWorkgroup}
        onOpenSettings={adminOnOpenSettings}
        onOpenPalette={onTogglePalette}
        onNewProfile={adminOnNewProfile}
        onNewWorkgroup={adminOnNewWorkgroup}
        onCloseSettings={closeSettings}
        onSetSettingsTarget={setSettingsTarget}
        onTogglePin={onTogglePin}
        onSetHostConnection={onSetHostConnection}
        onAddHostConnection={onAddHostConnection}
        onForgetHostConnection={onForgetHostConnection}
        onRefreshHostConnectionStatus={onRefreshHostConnectionStatus}
        autoOpenConnectionSwitcher={autoOpenConnectionSwitcher}
        onOpenNotifications={onOpenNotifications}
        notificationsUnread={notificationsUnread}
      />
      <main className={styles.main}>
          {view.kind === "settings" && canAdminEarly ? (
            <Settings
              profiles={profiles}
              workgroups={workgroups}
              target={settingsTarget}
              hostConnections={hostConnections}
              activeConnection={activeConnection}
              refreshTick={settingsRefreshTick}
              pinned={pinned}
              jumpHints={jumpHints}
              onTogglePin={onTogglePin}
              onSelectTarget={setSettingsTarget}
              onRefresh={reload}
              onOpenChat={closeSettings}
              onSetHostConnection={onSetHostConnection}
              onAddHostConnection={onAddHostConnection}
              onForgetHostConnection={onForgetHostConnection}
              onRefreshHostConnectionStatus={onRefreshHostConnectionStatus}
            />
          ) : (
            <>
              {daemonOffline && (
                <Banner
                  kind={isLocalAutostartInFlight ? "info" : "danger"}
                  pulsing={!isLocalAutostartInFlight}
                  action={isLocalAutostartInFlight ? null : "Retry"}
                  onAction={isLocalAutostartInFlight ? null : onRefreshHostConnectionStatus}
                >
                  {activeConnection?.status === "auth-failed"
                    ? `${activeConnection?.name ?? "Remote"} — token rejected. Re-pair device from Settings.`
                    : activeConnection?.kind === "remote"
                      ? `${activeConnection?.name ?? "Remote"} unreachable — check network / tunnel.`
                      : isLocalAutostartInFlight
                        ? "Starting local daemon…"
                        : autostartPhase === "gave-up"
                          ? "Local daemon won't start — check Settings → daemon, or run `alpi daemon start` from terminal."
                          : "Local daemon unreachable — reconnecting…"}
                </Banner>
              )}
              {view.kind === "workgroup" && activeWorkgroup && (
                <WorkgroupView
                  key={`${hostConnections.active_id}/${activeWorkgroup.profile}/${activeWorkgroup.id}`}
                  workgroup={activeWorkgroup}
                  profiles={profiles}
                  connectionId={hostConnections.active_id}
                  onReload={reload}
                  daemonOffline={daemonOffline}
                  onActiveTask={(task) => {
                    setActiveTask(task);
                    if (task == null) return;
                    const key = `${activeWorkgroup.profile}/${activeWorkgroup.id}`;
                    setTaskByWorkgroup((prev) =>
                      prev[key] === task ? prev : { ...prev, [key]: task },
                    );
                  }}
                  onOpenSettings={canAdminEarly ? (wg) => {
                    setSettingsTarget({ kind: "workgroup", id: wg.id, profile: wg.profile });
                    setView({ kind: "settings" });
                  } : null}
                  searchOpen={searchOpen}
                  onCloseSearch={onCloseSearch}
                />
              )}
              {(view.kind === "empty" || view.kind === "profile") && (
                <ChatPane
                  view={view}
                  profiles={profiles}
                  activeProfile={activeProfile}
                  connectionId={hostConnections.active_id}
                  sessionData={sessionData}
                  daemonOffline={daemonOffline}
                  pendingTurn={
                    pendingTurn && pendingTurn.profile === activeProfile?.name
                      ? pendingTurn
                      : null
                  }
                  onSend={onSend}
                  onCancel={onCancelTurn}
                  onConfigureProfile={canAdminEarly ? (p) => {
                    setSettingsTarget({ kind: "profile", id: p.name });
                    setView({ kind: "settings" });
                  } : null}
                  onSelectProfile={(name) => {
                    setPickerAlpi(name);
                    if (view.kind === "profile") {
                      const p = profiles.find((x) => x.name === name);
                      if (p) onOpenProfile(p);
                    }
                  }}
                  onRewriteMessage={onRewriteMessage}
                  onRetryMessage={onRetryMessage}
                  rewriteDraft={rewriteDraft}
                  onRewriteDraftApplied={() => {
                    setRewriteDraft((prev) =>
                      prev ? { ...prev, consumed: true } : prev,
                    );
                  }}
                  onOpenSkills={onBrowseSkills}
                  onOpenMemory={onBrowseMemory}
                  onOpenTools={onBrowseTools}
                  onRefreshSession={onRefreshSession}
                  onNewSession={onNewSessionForCurrentProfile}
                  onChangeSession={onChangeSession}
                  searchOpen={searchOpen}
                  onCloseSearch={onCloseSearch}
                  recents={recents}
                  onOpenRecent={onOpenRecent}
                />
              )}
            </>
          )}
      </main>
      <CommandPalette
        open={paletteOpen}
        onClose={onClosePalette}
        commands={paletteCommands}
        profiles={profiles}
        workgroups={workgroups}
      />
      <ToolsPanel
        open={browse === "tools"}
        onClose={onCloseBrowse}
        profile={view.kind === "profile" ? view.profile : null}
      />
      <SkillsPanel
        open={browse === "skills"}
        onClose={onCloseBrowse}
        profile={view.kind === "profile" ? view.profile : null}
      />
      <MemoryPanel
        open={browse === "memory"}
        onClose={onCloseBrowse}
        profile={view.kind === "profile" ? view.profile : null}
      />
      <CreateProfileModal
        open={createProfileOpen}
        existingNames={profiles.map((p) => p.name)}
        onClose={() => setCreateProfileOpen(false)}
        onCreated={async (profileName) => {
          setCreateProfileOpen(false);
          await reload();
          setSettingsTarget({ kind: "profile", id: profileName });
          setView({ kind: "settings" });
        }}
      />
      <CreateWorkgroupModal
        open={createWorkgroupOpen}
        profiles={profiles}
        connectionId={hostConnections.active_id}
        onClose={() => setCreateWorkgroupOpen(false)}
        onCreated={async (wgId, hubName) => {
          setCreateWorkgroupOpen(false);
          await reload();
          if (wgId) {
            // The creator just made it — it's not "unread".
            markWorkgroupRead(hostConnections.active_id, hubName, wgId);
            setSettingsTarget({ kind: "workgroup", id: wgId, profile: hubName });
            setView({ kind: "settings" });
          }
        }}
      />
      <ApprovalModal requests={approvalQueue} onResolved={onApprovalResolved} />
      <ClarificationModal requests={clarificationQueue} onResolved={onClarificationResolved} />
      <NotificationsModal
        open={notificationsOpen}
        onClose={onCloseNotifications}
        profiles={profiles}
        connectionId={hostConnections.active_id}
        selectedId={notificationsTarget?.id}
        selectedProfile={notificationsTarget?.profile}
        onOpenChat={(profile, sessionId) =>
          setView({ kind: "profile", profile, sessionId: sessionId || null })
        }
        onOpenSchedule={(profile) => {
          setSettingsTarget({ kind: "profile", id: profile });
          setView({ kind: "settings" });
        }}
      />
    </div>
  );
}
