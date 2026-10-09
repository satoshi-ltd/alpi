import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { RATE_LIMITED, RATE_LIMITED_MESSAGE } from "./lib/connection-status.js";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { safeUnlisten } from "./lib/tauri-listen.js";
import Sidebar from "./features/Sidebar.jsx";
import ChatPane from "./pages/ChatPane.jsx";
import WorkgroupView from "./pages/WorkgroupView.jsx";
import WorkgroupsView from "./pages/WorkgroupsView.jsx";
import Settings from "./pages/Settings.jsx";
import { Banner, Button, EmptyState } from "./primitives/index.js";
import { EMPTY } from "../../common/emptyCopy.mjs";
import { useNotify } from "./primitives/Notification.jsx";
import CommandPalette from "./features/CommandPalette.jsx";
import ActivityPanel from "./features/ActivityPanel.jsx";
import ShortcutsSheet from "./features/ShortcutsSheet.jsx";
import ApprovalModal from "./features/ApprovalModal.jsx";
import ClarificationModal from "./features/ClarificationModal.jsx";
import { splitInline } from "./lib/inlineRequests.js";
import CreateProfileModal from "./features/CreateProfileModal.jsx";
import CreateWorkgroupModal from "./features/CreateWorkgroupModal.jsx";
import NotificationsModal from "./features/NotificationsModal.jsx";
import ProfilePanels from "./features/ProfilePanels.jsx";
import { useCommands } from "./hooks/useCommands.js";
import { orderedJumpTargets } from "./lib/profile-order.js";
import LoadFailed from "./primitives/LoadFailed.jsx";
import { LANDING_VIEW, firstRosterProfile, newSessionProfile, profileLandingView, swapPreviousView, viewLeavingSettings } from "./lib/landing.js";
import { profileLabel } from "./lib/profile-display.js";
import { installUpdater } from "./lib/updater.js";
import { cycleTheme } from "./lib/theme.js";
import { findLatestTask } from "./lib/workgroup-tasks.js";
import { saveCachedMessages } from "./lib/workgroup-cache.js";
import { fetchWorkgroupTranscript, invalidateTranscriptCache } from "./lib/workgroup-fetch.js";
import { invalidateSessionCache } from "./lib/session-cache.js";
import { createSessionOpener } from "./lib/session-open.js";
import { watchAcceptance } from "./lib/chat-acceptance.js";
import { connectionCanManage } from "./lib/connection-access.js";
import { describeConnectionError } from "./lib/connection-status.js";
import { createSessionRefresher } from "./lib/session-refresh.js";
import { invalidateConnectionCaches } from "./lib/swr-cache.js";
import { invalidateSessionsButtonCache } from "./primitives/SessionsButton.jsx";
import {
  classifyDaemonPayload,
  fromDaemonFrame,
  isActiveWorkgroupView,
} from "./lib/daemon-frame.js";
import { subscribeDaemonEvent } from "./lib/daemon-bus.js";
import { pendingTurnForView } from "./lib/pendingTurnForView.js";
import { enqueueRequest as enqueueApprovalRequest } from "./lib/approval-queue.js";
import { enqueueRequest as enqueueClarificationRequest } from "./lib/clarification-queue.js";
import { invalidateProfileDetailCache } from "./hooks/useProfileDetail.js";
import { useCoalescedCallback } from "./hooks/useCoalescedCallback.js";
import { usePendingQueue } from "./hooks/usePendingQueue.js";
import { rosterStates, useActivity } from "./hooks/useActivity.js";
import { useChatStream } from "./hooks/useChatStream.js";
import { useHostConnections } from "./hooks/useHostConnections.js";
import { useAllOutputs } from "./hooks/useOutputs.js";
import { useNavListener } from "./hooks/useNavListener.js";
import { usePinned } from "./hooks/usePinned.js";
import { useActiveRole } from "./hooks/useActiveRole.js";
import { useCloseAdminSurfacesOnDemotion } from "./hooks/useCloseAdminSurfacesOnDemotion.js";
import { useWorkgroupTasks } from "./hooks/useWorkgroupTasks.js";
import { markWorkgroupRead } from "./hooks/useReadState.js";
import { isTtsActive, subscribeTts } from "./lib/tts.js";
import { useWindowChrome } from "./hooks/useWindowChrome.js";
import {
  useActiveViewPing,
  useNotificationDeeplink,
} from "./hooks/useNotificationDeeplink.js";
import { useLocalDaemon } from "./hooks/useLocalDaemon.js";
import Welcome, { FirstRunHint, firstRunHintSeen, markFirstRunHintSeen } from "./features/Welcome.jsx";
import { useDelayedFlag } from "./lib/useDelayedFlag.js";
import { hasDirtySettings } from "./lib/settingsDirty.js";
import styles from "./App.module.css";

function isChatSessionSummary(session) {
  return session?.kind === "chat";
}

export function isChatSessionData(data) {
  // kind comes from the daemon envelope and classifies the TRUE first turn — turns[0] of a tail slice does not, so offset slices without kind are unclassifiable and must pass.
  if (typeof data?.kind === "string") return data.kind === "chat" || data.kind === "empty";
  if (Number.isInteger(data?.turnsOffset) && data.turnsOffset > 0) return true;
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

export function profileManagementAllowed(role) {
  return role !== "member";
}

export function canRefreshProfileThread(view, sessionData) {
  if (view?.kind === "workgroup") return true;
  if (view?.kind !== "profile") return false;
  return view.sessionId != null || (sessionData?.turns?.length ?? 0) > 0;
}

export function connectionFailureMessage(connection) {
  if (connection?.status === "disabled") {
    return `${connection?.name ?? "Remote"} — connection disabled by host. Ask an admin to enable it in Settings → Connections.`;
  }
  if (connection?.status === "auth-failed") {
    return `${connection?.name ?? "Remote"} — token rejected. Re-pair device from Settings.`;
  }
  if (connection?.status === RATE_LIMITED) {
    return `${connection?.name ?? "Remote"} — ${RATE_LIMITED_MESSAGE}`;
  }
  return null;
}

export function settingsTargetAfterExit(target, previous) {
  if (target?.kind !== "connections") return target;
  if (previous?.kind === "profile" || previous?.kind === "workgroup") return previous;
  return { kind: "profile", id: null };
}

export function profileSurfaceKey(surface, connectionId, profile) {
  // Sibling modals share connection+profile: without the surface prefix React collapses all but one.
  return `${surface}:${connectionId ?? ""}:${profile ?? ""}`;
}

export function turnBlocksSend(turn) {
  return !!turn && !turn.error && !turn.settling;
}

export function settingsTargetForChatView(view, selectedProfile = null) {
  if (view?.kind === "profile") return { kind: "profile", id: view.profile };
  if (view?.kind === "workgroup") return { kind: "workgroup", id: view.id };
  return { kind: "profile", id: selectedProfile };
}

export default function App() {
  const notify = useNotify();
  const [view, setView] = useState(LANDING_VIEW);
  const [settingsTarget, setSettingsTarget] = useState({
    kind: "profile",
    id: null,
  });
  const settingsBeforeConnectionsRef = useRef(null);
  const openConnections = useCallback(() => {
    if (settingsTarget?.kind !== "connections") {
      settingsBeforeConnectionsRef.current = settingsTarget;
    }
    setSettingsTarget({ kind: "connections" });
  }, [settingsTarget]);
  const closeConnections = useCallback(() => {
    setSettingsTarget(
      settingsBeforeConnectionsRef.current || { kind: "profile", id: null },
    );
  }, []);
  const [sessionData, setSessionData] = useState(null);
  const [sessionSync, setSessionSync] = useState(null);
  const sessionDataRef = useRef(null);
  useEffect(() => {
    sessionDataRef.current = sessionData;
  }, [sessionData]);
  const [rewriteDraft, setRewriteDraft] = useState(null);
  const [pendingAttachment, setPendingAttachment] = useState(null);
  const [activeTask, setActiveTask] = useState(null);

  const viewRef = useRef(view);
  const prevViewRef = useRef(view);
  const prevViewsRef = useRef({});
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
  useActiveViewPing(view);

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
  useEffect(() => {
    if (view.kind === "settings" || settingsTarget?.kind !== "connections") return;
    const next = settingsTargetAfterExit(settingsTarget, settingsBeforeConnectionsRef.current);
    settingsTargetRef.current = next;
    setSettingsTarget(next);
  }, [view.kind, settingsTarget]);
  const workgroupsRef = useRef([]);

  const reloadRef = useRef(null);
  const foregroundTurnRef = useRef(null);
  const activeConnectionIdRef = useRef(null);
  const newSessionProfileRef = useRef(() => null);

  const jumpTargetsRef = useRef([]);
  const panelGuardRef = useRef(null);
  const onJumpToProfile = useCallback((index) => {
    const item = jumpTargetsRef.current[index];
    if (!item) return;
    if (panelGuardRef.current && !panelGuardRef.current()) return;
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
  const canManageProfileSurfaces = profileManagementAllowed(activeRole);
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
  const [sidebarSearchOpen, setSidebarSearchOpen] = useState(false);
  const sidebarSearchAvailableRef = useRef(false);
  const onToggleSidebarSearch = useCallback(
    () => setSidebarSearchOpen((v) => !v),
    [],
  );
  const onCloseSidebarSearch = useCallback(() => setSidebarSearchOpen(false), []);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const paletteOpenRef = useRef(false);
  useEffect(() => {
    paletteOpenRef.current = paletteOpen;
  }, [paletteOpen]);
  const onTogglePalette = useCallback(() => {
    setPaletteOpen((v) => !v);
  }, []);
  const onClosePalette = useCallback(() => setPaletteOpen(false), []);
  const [activityOpen, setActivityOpen] = useState(false);
  const onToggleActivity = useCallback(() => setActivityOpen((v) => !v), []);
  const onCloseActivity = useCallback(() => setActivityOpen(false), []);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const onToggleShortcuts = useCallback(() => {
    setPaletteOpen(false);
    setShortcutsOpen((v) => !v);
  }, []);
  const onCloseShortcuts = useCallback(() => setShortcutsOpen(false), []);

  const [browse, setBrowse] = useState(null);
  const [sessionsDropdownOpenTick, setSessionsDropdownOpenTick] = useState(0);
  const [taskHistoryOpenTick, setTaskHistoryOpenTick] = useState(0);
  const [readAloudTick, setReadAloudTick] = useState(0);
  const [readAloudActive, setReadAloudActive] = useState(() => isTtsActive());
  const [workgroupRefreshTick, setWorkgroupRefreshTick] = useState(0);
  const [workgroupPauseTick, setWorkgroupPauseTick] = useState(0);
  const [scheduleJob, setScheduleJob] = useState(null);
  const onCloseBrowse = useCallback(() => { setBrowse(null); setScheduleJob(null); }, []);
  const panelsMayLeave = useCallback(() => !panelGuardRef.current || panelGuardRef.current(), []);
  const onBrowseTools = useCallback(() => { if (panelsMayLeave()) setBrowse("tools"); }, [panelsMayLeave]);
  const onBrowseSkills = useCallback(() => { if (panelsMayLeave()) setBrowse("skills"); }, [panelsMayLeave]);
  const onBrowseMemory = useCallback(() => { if (panelsMayLeave()) setBrowse("memory"); }, [panelsMayLeave]);
  const onBrowseSchedule = useCallback(() => {
    if (!panelsMayLeave()) return;
    setScheduleJob(null);
    setBrowse("schedule");
  }, [panelsMayLeave]);
  const resetAdminSurfaces = useCallback(() => {
    setBrowse(null);
    setScheduleJob(null);
    setNotificationsOpen(false);
  }, []);
  useCloseAdminSurfacesOnDemotion(canManageProfileSurfaces, resetAdminSurfaces);
  useEffect(() => subscribeTts(() => setReadAloudActive(isTtsActive())), []);
  const onToggleReadAloud = useCallback(() => {
    setReadAloudTick((n) => n + 1);
  }, []);
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
  // Member devices have no Settings surface — snap back to the landing if state ever points there (deeplink, nav event, ⌘, race).
  useEffect(() => {
    if (!canAdminEarly && view.kind === "settings") {
      setView(LANDING_VIEW);
    }
  }, [canAdminEarly, view.kind]);
  const leavingSettingsView = (target = settingsTargetRef.current) =>
    viewLeavingSettings({
      target,
      previous: prevViewRef.current,
      profiles: profilesRef.current,
      workgroups: workgroupsRef.current,
    });
  const onOpenSettings = useCallback(() => {
    const v = viewRef.current;
    if (v?.kind === "settings") {
      setView(leavingSettingsView());
      return;
    }
    const next = settingsTargetForChatView(v, newSessionProfileRef.current());
    settingsTargetRef.current = next;
    setSettingsTarget(next);
    setView({ kind: "settings" });
  }, []);
  const adminOnOpenSettings = canAdminEarly ? onOpenSettings : null;
  const openSettingsFor = useCallback((target) => {
    setSettingsTarget(target);
    setView({ kind: "settings" });
  }, []);
  const adminOpenSettingsFor = canAdminEarly ? openSettingsFor : null;
  useNavListener(setView);

  const connectionOnlineRef = useRef(true);
  const { pendingTurns, pendingTurnsRef, startTurn, removeTurn, clearTurnsForConnection, detachNewChatTurns } = useChatStream({
    setSessionData,
    setView,
    setRewriteDraft,
    reloadRef,
    notify,
    connectionOnlineRef,
    activeConnectionIdRef,
    sessionDataRef,
  });

  const {
    hostConnections,
    hostConnectionsRef,
    profiles,
    setProfiles,
    workgroups,
    dropWorkgroup,
    connectionSyncing,
    connectionSwitching,
    rosterAnswered,
    rosterSettled,
    rosterGeneration,
    onLocalDaemonStarted,
    touchWorkgroup,
    reload,
    onSetHostConnection,
    onAddHostConnection,
    onForgetHostConnection,
    onRenameHostConnection,
    onRefreshHostConnectionStatus,
  } = useHostConnections({
    setSessionData,
    clearTurnsForConnection,
    setRewriteDraft,
    setActiveTask,
    setView,
    notify,
  });

  useEffect(() => {
    activeConnectionIdRef.current = hostConnections.active_id;
  }, [hostConnections.active_id]);

  const startNewThread = useCallback((name) => {
    if (!name) return;
    if (viewRef.current?.kind === "settings" && hasDirtySettings()) {
      window.notify?.("Save or discard your settings changes first", { variant: "info" });
      return;
    }
    detachNewChatTurns(hostConnectionsRef.current?.active_id ?? null, name);
    setRewriteDraft(null);
    setView({ kind: "profile", profile: name, sessionId: null });
  }, [detachNewChatTurns, hostConnectionsRef]);
  const onNewSessionWith = useCallback((profile) => startNewThread(profile?.name), [startNewThread]);
  const onNewSession = useCallback(() => startNewThread(newSessionProfileRef.current()), [startNewThread]);

  const approval = usePendingQueue({
    command: "approval_pending",
    connectionId: hostConnections.active_id,
    enqueue: enqueueApprovalRequest,
  });
  const clarification = usePendingQueue({
    command: "clarification_pending",
    connectionId: hostConnections.active_id,
    enqueue: enqueueClarificationRequest,
  });

  const focusPendingRequest = useCallback((request) => {
    const queue = request.kind === "clarification" ? clarification : approval;
    queue.refetch().then(() => queue.promote(request.id));
  }, [approval, clarification]);
  const openScheduleFor = useCallback((profile) => {
    if (!panelsMayLeave()) return;
    if (viewRef.current?.kind !== "profile" || viewRef.current.profile !== profile) {
      setView({ kind: "profile", profile, sessionId: null });
    }
    setScheduleJob(null);
    setBrowse("schedule");
  }, [panelsMayLeave]);

  const canOpenScheduleOn = useCallback(
    (connectionId) => connectionCanManage(hostConnectionsRef.current?.connections, connectionId),
    [],
  );

  useNotificationDeeplink({
    setView,
    setSettingsTarget,
    openNotifications: openNotificationsForDeeplink,
    onSwitchConnection: onSetHostConnection,
    activeConnectionId: hostConnections.active_id,
    focusRequest: focusPendingRequest,
    openSchedule: openScheduleFor,
    canOpenSchedule: canOpenScheduleOn,
  });

  useEffect(() => {
    reloadRef.current = reload;
  }, [reload]);

  const onWorkgroupGone = useCallback((connectionId, profile, wgId) => {
    dropWorkgroup(connectionId, profile, wgId);
    const current = viewRef.current;
    if (
      hostConnectionsRef.current?.active_id === connectionId
      && current?.kind === "workgroup"
      && current.profile === profile
      && current.id === wgId
    ) {
      setView({ kind: "workgroups" });
    }
  }, [dropWorkgroup, hostConnectionsRef]);

  const { rows: unreadOutputs } = useAllOutputs({
    connections: hostConnections.connections,
    status: "unread",
    activeId: hostConnections.active_id,
  });
  const notificationsUnread = unreadOutputs.length;
  const trayUnread = canManageProfileSurfaces ? notificationsUnread : 0;

  useEffect(() => {
    invoke("tray_announce_notifications", { unread: trayUnread }).catch(() => {});
  }, [trayUnread]);

  // The tray listener registers once; a ref feeds it the live permission so a member-connection click can't arm the modal (which would then pop open on the next switch to admin).
  const notificationsAllowedRef = useRef(canManageProfileSurfaces);
  notificationsAllowedRef.current = canManageProfileSurfaces;
  useEffect(() => {
    let cancelled = false;
    let unlisten = null;
    listen("tray:notifications-clicked", () => {
      if (!notificationsAllowedRef.current) return;
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

  // On connection switch drop cache for BOTH prev and new active: events from the new daemon weren't received while we were elsewhere, so anything still cached for it is potentially stale.
  const prevConnectionIdRef = useRef(hostConnections.active_id);
  useEffect(() => {
    const prev = prevConnectionIdRef.current;
    if (prev !== hostConnections.active_id) {
      if (prev) {
        invalidateTranscriptCache(prev);
        invalidateProfileDetailCache(prev);
        invalidateSessionCache(prev);
      }
      invalidateTranscriptCache(hostConnections.active_id);
      invalidateProfileDetailCache(hostConnections.active_id);
      invalidateSessionCache(hostConnections.active_id);
      invalidateConnectionCaches(prev);
      invalidateConnectionCaches(hostConnections.active_id);
      invalidateSessionsButtonCache();
    }
    if (prev !== hostConnections.active_id) {
      const swapped = swapPreviousView(prevViewsRef.current, prev, hostConnections.active_id, prevViewRef.current);
      prevViewsRef.current = swapped.saved;
      prevViewRef.current = swapped.previous;
    }
    prevConnectionIdRef.current = hostConnections.active_id;
  }, [hostConnections.active_id]);

  const profilesRef = useRef(profiles);
  useEffect(() => {
    profilesRef.current = profiles;
  }, [profiles]);
  const onDeleteProfile = useCallback(async (name) => {
    const snapshot = profilesRef.current;
    setProfiles((prev) => prev.filter((p) => p.name !== name));
    const v = viewRef.current;
    const t = settingsTargetRef.current;
    const viewingDeleted =
      (v?.kind === "profile" && v.profile === name) ||
      (v?.kind === "settings" && t?.kind === "profile" && t.id === name);
    if (viewingDeleted) setView(LANDING_VIEW);
    try {
      await invoke("profile_delete", { name, connectionId: hostConnectionsRef.current?.active_id ?? null });
      window.notify?.(`Profile @${name} deleted`, { variant: "success" });
      reload();
    } catch (e) {
      setProfiles(snapshot);
      window.notify?.(`Delete @${name} failed: ${String(e)}`, { variant: "error" });
    }
  }, [setProfiles, reload]);
  const adminOnDeleteProfile = canAdminEarly ? onDeleteProfile : null;
  const onTogglePauseProfile = useCallback((profile) => {
    const next = !profile.paused;
    setProfiles((prev) => prev.map((p) => (p.name === profile.name ? { ...p, paused: next } : p)));
    invoke("set_config_field", { profile: profile.name, key: "paused", value: next ? "true" : "false" })
      .then(() => reload())
      .catch((e) => {
        setProfiles((prev) => prev.map((p) => (p.name === profile.name ? { ...p, paused: !next } : p)));
        window.notify?.(`Pause @${profileLabel(profile.name)} failed: ${String(e)}`, { variant: "error" });
      });
  }, [setProfiles, reload]);
  const adminOnTogglePauseProfile = canAdminEarly ? onTogglePauseProfile : null;
  useEffect(() => {
    const conn = hostConnections.connections.find(
      (c) => c.id === hostConnections.active_id,
    );
    // Unknown/probing stay truthy — only a confirmed-dead daemon pauses pollers.
    connectionOnlineRef.current =
      conn?.status !== "offline" &&
      conn?.status !== "disabled" &&
      conn?.status !== "auth-failed" &&
      conn?.status !== RATE_LIMITED;
  }, [hostConnections]);
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

  // A deleted/forbidden session must not survive as a cached ghost transcript.
  const { refresh: refreshSessionData, dropDeadSession } = useMemo(
    () =>
      createSessionRefresher({
        activeConnectionIdRef,
        sessionDataRef,
        viewRef,
        setSessionData,
        clearViewSession: (profile, sessionId) =>
          setView((v) =>
            v.kind === "profile" && v.profile === profile && v.sessionId === sessionId
              ? { ...v, sessionId: null }
              : v,
          ),
        isChatSessionData,
      }),
    [],
  );

  const [sessionLoadError, setSessionLoadError] = useState(null);
  const sessionOpener = useMemo(
    () =>
      createSessionOpener({
        activeConnectionIdRef,
        sessionDataRef,
        setSessionData,
        setSessionSync,
        isChatSessionData,
        onGone: (connId, profile, sessionId) => dropDeadSession(connId, profile, sessionId),
        onNonChat: (_connId, _profile, sessionId) =>
          setView((v) =>
            v.kind === "profile" && v.sessionId === sessionId
              ? { ...v, sessionId: null }
              : v,
          ),
        onError: (e, _connId, profile, sessionId) => {
          if (sessionDataRef.current?.turns?.length > 0) {
            notify({ message: `session refresh failed: ${e}`, variant: "error" });
            return;
          }
          setSessionLoadError({ key: `${profile}:${sessionId}`, message: String(e) });
        },
      }),
    [],
  );

  const [sessionRetryTick, setSessionRetryTick] = useState(0);
  useEffect(() => {
    setSessionSync(null);
    setSessionLoadError(null);
    if (view.kind !== "profile" || !view.sessionId) {
      setSessionData(null);
      return undefined;
    }
    return sessionOpener.open(view.profile, view.sessionId);
  }, [view, hostConnections.active_id, sessionOpener, sessionRetryTick]);
  const sessionLoadFailure = view.kind === "profile" && sessionLoadError?.key === `${view.profile}:${view.sessionId}`
    ? sessionLoadError.message
    : null;

  const scheduleReload = useCoalescedCallback(() => reloadRef.current?.(), 500, 5000);
  const schedulePendingSync = useCoalescedCallback(() => {
    approval.refetch();
    clarification.refetch();
  }, 300, 3000);

  const scheduleSessionRefresh = useCoalescedCallback((profile, sessionId) => {
    refreshSessionData(profile, sessionId);
  }, 350);

  const onRefreshSession = useCallback(() => {
    const v = viewRef.current;
    if (v?.kind === "profile" && v.profile && v.sessionId) {
      refreshSessionData(v.profile, v.sessionId);
    }
    reloadRef.current?.();
  }, [refreshSessionData]);

  const applyChange = useCallback((ev) => {
    if (!ev || !ev.kind) return;
    const v = viewRef.current;
    switch (ev.kind) {
      case "session": {
        const activeConnectionId = hostConnectionsRef.current?.active_id ?? null;
        const liveForSession = Object.values(pendingTurnsRef.current).some(
          (t) =>
            (t.connectionId ?? null) === activeConnectionId &&
            t.profile === ev.profile &&
            (t.sessionId ?? t.launchSessionId) === ev.session_id,
        );
        if (
          v.kind === "profile" &&
          v.profile === ev.profile &&
          v.sessionId === ev.session_id &&
          !liveForSession
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
        // No reload and no fetch for background workgroups: the badge comes from the activity map, unread/ordering from the local mtime patch. Transcript work happens only for the open view.
        touchWorkgroup(ev.profile, ev.wg_id);
        if (!isActiveWorkgroupView(v, ev)) break;
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
  }, [scheduleReload, schedulePendingSync, scheduleSessionRefresh, setActivityByWorkgroup, setTaskByWorkgroup, seenMtimesRef, touchWorkgroup]);

  useEffect(() => {
    let cancelled = false;
    let unlistenFs = null;
    listen("fs-change", (e) => applyChange(e.payload))
      .then((fn) => {
        if (cancelled) safeUnlisten(fn);
        else unlistenFs = fn;
      })
      .catch(() => {});
    const unsubDaemon = subscribeDaemonEvent((e) => {
      const payload = e.payload ?? {};
      const cls = classifyDaemonPayload(
        payload,
        hostConnectionsRef.current?.active_id,
      );
      if (cls === "drop") return;
      const frame = payload.frame ?? payload;
      if (cls === "replay") {
        // Reconnect backfill (up to 200 frames in a burst): one coalesced reload covers state catch-up; per-event fetch fan-out would hammer the freshly restarted daemon.
        if (fromDaemonFrame(frame)) scheduleReload();
        if (/^(approval|clarification)\./.test(String(frame?.event ?? ""))) schedulePendingSync();
        return;
      }
      // approval.request: enqueue caution prompt. approval.resolved: pop in case another client answered first.
      if (frame?.event === "approval.request") {
        approval.merge(frame.data ?? {});
        return;
      }
      if (frame?.event === "approval.resolved") {
        const rid = frame.data?.request_id;
        if (rid) approval.resolve(rid);
        return;
      }
      if (frame?.event === "clarification.request") {
        clarification.merge(frame.data ?? {});
        return;
      }
      if (frame?.event === "clarification.resolved") {
        const rid = frame.data?.request_id;
        if (rid) clarification.resolve(rid);
        return;
      }
      const mapped = fromDaemonFrame(frame);
      if (mapped) applyChange(mapped);
    });
    return () => {
      cancelled = true;
      safeUnlisten(unlistenFs);
      unsubDaemon();
    };
  }, [applyChange, hostConnectionsRef, approval.merge, approval.resolve, clarification.merge, clarification.resolve, scheduleReload]);

  const sendingRef = useRef(false);
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

  const activeProfile = useMemo(() => {
    if (view.kind === "profile") {
      return profiles.find((p) => p.name === view.profile) ?? null;
    }
    if (view.kind === "settings" && settingsTarget?.kind === "profile") {
      return (
        profiles.find((p) => p.name === settingsTarget.id) ?? profiles[0] ?? null
      );
    }
    return null;
  }, [view, profiles, settingsTarget]);
  const activeProfileName = activeProfile?.name ?? null;
  const panelOwner = useMemo(
    () => (activeProfile ? { name: activeProfile.name, fold: activeProfile.fold, accent: activeProfile.accent } : null),
    [activeProfile],
  );
  const historyKind = activeWorkgroup || activeSettingsWorkgroup
    ? "tasks"
    : activeProfileName ? "sessions" : null;
  const canReadAloud = view.kind === "profile" && (sessionData?.turns ?? []).some((t) => t?.assistant);
  const onOpenHistory = useCallback(() => {
    if (activeWorkgroup) {
      setTaskHistoryOpenTick((n) => n + 1);
      return;
    }
    if (activeSettingsWorkgroup) {
      setView({
        kind: "workgroup",
        profile: activeSettingsWorkgroup.profile,
        id: activeSettingsWorkgroup.id,
      });
      setTaskHistoryOpenTick((n) => n + 1);
      return;
    }
    if (activeProfileName) {
      if (view.kind !== "profile" || view.profile !== activeProfileName) {
        setView({
          kind: "profile",
          profile: activeProfileName,
          sessionId: isChatSessionSummary(activeProfile?.latest_session)
            ? activeProfile.latest_session.id
            : null,
        });
      }
      setSessionsDropdownOpenTick((n) => n + 1);
    }
  }, [activeWorkgroup, activeSettingsWorkgroup, activeProfileName, activeProfile, view]);

  const onRefreshActiveThread = useCallback(() => {
    const v = viewRef.current;
    if (v?.kind === "profile") {
      onRefreshSession();
    } else if (v?.kind === "workgroup") {
      setWorkgroupRefreshTick((n) => n + 1);
    }
  }, [onRefreshSession]);

  const onToggleActiveProfilePause = useCallback(() => {
    if (activeProfile && adminOnTogglePauseProfile) {
      adminOnTogglePauseProfile(activeProfile);
    }
  }, [activeProfile, adminOnTogglePauseProfile]);

  const onToggleActiveWorkgroupPause = useCallback(() => {
    if (activeWorkgroup) setWorkgroupPauseTick((n) => n + 1);
  }, [activeWorkgroup]);

  const onToggleActiveContextPause = useCallback(() => {
    const v = viewRef.current;
    if (v?.kind === "profile") {
      onToggleActiveProfilePause();
    } else if (v?.kind === "workgroup") {
      onToggleActiveWorkgroupPause();
    }
  }, [onToggleActiveProfilePause, onToggleActiveWorkgroupPause]);

  const activityOnline = hostConnections.connections.find((c) => c.id === hostConnections.active_id)?.status === "online";
  const { activity, supported: activitySupported, counts: activityCounts } = useActivity({
    connectionId: hostConnections.active_id,
    online: activityOnline,
  });
  const rosterState = useMemo(
    () => (activitySupported ? rosterStates(activity) : null),
    [activity, activitySupported],
  );
  const onToggleActivityIfSupported = activitySupported ? onToggleActivity : null;
  useEffect(() => {
    if (!activitySupported) setActivityOpen(false);
  }, [activitySupported]);
  const accentByProfile = useMemo(() => {
    const out = {};
    for (const p of profiles) out[p.name] = p.accent ?? null;
    return out;
  }, [profiles]);
  const foldByProfile = useMemo(() => {
    const out = {};
    for (const p of profiles) out[p.name] = p.fold;
    return out;
  }, [profiles]);
  const onReviewActivity = useCallback((item) => {
    if (item?.profile && item.session_id) {
      setRewriteDraft(null);
      setView({ kind: "profile", profile: item.profile, sessionId: item.session_id });
    }
    const q = item?.kind === "clarification" ? clarification : approval;
    q.refetch().then(() => q.promote(item.request_id));
  }, [approval, clarification]);

  const newSessionAvailable = profiles.length > 0;
  useWindowChrome({
    viewRef,
    onNewSession: newSessionAvailable ? onNewSession : null,
    onJumpToProfile,
    onNewProfile: adminOnNewProfile,
    onNewWorkgroup: adminOnNewWorkgroup,
    onOpenSettings: adminOnOpenSettings,
    onToggleSearch,
    onToggleSidebarSearch,
    sidebarSearchAvailableRef,
    onTogglePalette,
    paletteOpenRef,
    onClosePalette,
    activeProfileName,
    historyKind,
    onOpenHistory,
    onRefreshThread:
      view.kind === "profile" || view.kind === "workgroup"
        ? onRefreshActiveThread
        : null,
    onToggleContextPause:
      view.kind === "profile" || view.kind === "workgroup"
        ? onToggleActiveContextPause
        : null,
    onToggleReadAloud: canReadAloud ? onToggleReadAloud : null,
    onBrowseTools: canManageProfileSurfaces ? onBrowseTools : null,
    onBrowseSkills: canManageProfileSurfaces ? onBrowseSkills : null,
    onBrowseMemory: canManageProfileSurfaces ? onBrowseMemory : null,
    onBrowseSchedule: canManageProfileSurfaces ? onBrowseSchedule : null,
    onToggleNotifications: canManageProfileSurfaces ? onOpenNotifications : null,
    onToggleActivity: onToggleActivityIfSupported,
    onToggleShortcuts,
  });

  const pendingTurnForCurrentView = useMemo(
    () => pendingTurnForView({
      pendingTurns,
      view,
      activeProfileName: activeProfile?.name,
      activeConnectionId: hostConnections.active_id,
    }),
    [pendingTurns, view, activeProfile?.name, hostConnections.active_id],
  );
  useEffect(() => {
    foregroundTurnRef.current = pendingTurnForCurrentView;
  }, [pendingTurnForCurrentView]);
  const inlineScope = useMemo(() => ({
    profile: view.kind === "profile" ? view.profile : null,
    sessionIds: [view.sessionId, pendingTurnForCurrentView?.sessionId],
    live: !!pendingTurnForCurrentView,
  }), [view, pendingTurnForCurrentView]);
  const approvalSplit = useMemo(() => splitInline(approval.queue, inlineScope), [approval.queue, inlineScope]);
  const clarificationSplit = useMemo(() => splitInline(clarification.queue, inlineScope), [clarification.queue, inlineScope]);
  const pendingProfiles = useMemo(() => {
    const s = new Set();
    for (const t of Object.values(pendingTurns)) {
      if ((t.connectionId ?? null) === hostConnections.active_id) s.add(t.profile);
    }
    return s;
  }, [pendingTurns, hostConnections.active_id]);

  const onSend = useCallback(
    async (text, model, opts) => {
      const attachments = opts?.attachments?.length ? opts.attachments : null;
      if ((!text.trim() && !attachments) || !activeProfile) return false;
      if (activeProfile.paused) return false;
      if (sendingRef.current) return false;
      sendingRef.current = true;
      let held = true;
      const release = () => {
        if (!held) return;
        held = false;
        sendingRef.current = false;
      };
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

        const activeConnectionId = hostConnectionsRef.current?.active_id ?? null;
        const prior = Object.values(pendingTurnsRef.current).find((t) =>
          (t.connectionId ?? null) === activeConnectionId &&
          t.profile === profileName &&
          (startSessionId != null
            ? (t.sessionId ?? t.launchSessionId) === startSessionId
            : (t.launchSessionId ?? null) === null),
        );
        if (turnBlocksSend(prior)) {
          notify({ message: "A turn is already running in this session — wait for it or press Stop.", variant: "info" });
          return false;
        }
        if (prior) {
          removeTurn(prior.requestId);
        }

        const requestId = `desktop-${profileName}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

        startTurn({
          user: text,
          tools: [],
          error: null,
          profile: profileName,
          connectionId: activeConnectionId,
          sessionId: startSessionId,
          launchSessionId: startSessionId,
          requestId,
          attachments,
          rewriteFromTurn,
          at: Date.now() / 1000,
        });

        let wireAttachments = attachments;
        if (attachments) {
          const conns = hostConnectionsRef.current;
          const conn = conns?.connections?.find((c) => c.id === conns.active_id);
          if (conn && conn.kind !== "local") {
            try {
              wireAttachments = await Promise.all(
                attachments.map(async (a) => {
                  const staged = await invoke("attachment_stage", {
                    profile: profileName,
                    path: a.path,
                    mime: a.mime,
                    connectionId: activeConnectionId,
                  });
                  return { path: staged.path, name: staged.name, mime: staged.mime };
                }),
              );
            } catch (e) {
              notify({ message: `Attachment upload failed: ${e}`, variant: "error" });
              removeTurn(requestId);
              return false;
            }
          }
        }

        const acceptance = watchAcceptance(requestId);
        await acceptance.ready;
        try {
          await invoke("chat_send_stream", {
            profile: profileName,
            sessionId: startSessionId,
            rewriteFromTurn,
            text,
            model: model ?? null,
            requestId,
            attachments: wireAttachments,
            connectionId: activeConnectionId,
          });
        } catch (e) {
          acceptance.cancel();
          notify({ message: String(e), variant: "error" });
          removeTurn(requestId);
          return false;
        }
        release();
        const verdict = await acceptance.promise;
        if (!verdict.accepted) {
          removeTurn(requestId);
          notify({ message: describeConnectionError(verdict.text) || "The daemon did not take the message.", variant: "error" });
          return false;
        }
        return true;
      } finally {
        release();
      }
    },
    [activeProfile, view, rewriteDraft, notify, startTurn, removeTurn, pendingTurnsRef, hostConnectionsRef],
  );

  const onCancelTurn = useCallback(() => {
    const pending = foregroundTurnRef.current;
    if (!pending?.profile) return;
    invoke("chat_cancel", {
      profile: pending.profile,
      requestId: pending.requestId,
      connectionId: pending.connectionId ?? null,
    }).catch(() => {});
  }, []);

  const onSelectWorkgroup = useCallback((wg) => {
    setView({ kind: "workgroup", profile: wg.profile, id: wg.id });
  }, []);

  const onOpenProfile = useCallback((profile) => {
    setRewriteDraft(null);
    setView(profileLandingView(profile));
  }, []);

  const onChangeSession = useCallback((sessionId) => {
    setRewriteDraft(null);
    setView((v) => (v.kind === "profile" ? { ...v, sessionId } : v));
  }, []);

  const onNewSessionForCurrentProfile = useCallback(() => {
    const v = viewRef.current;
    if (v?.kind === "profile") startNewThread(v.profile);
  }, [startNewThread]);

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

  const onViewAllWorkgroups = useCallback(() => {
    setView({ kind: "workgroups" });
  }, []);

  const closeSettings = useCallback(() => {
    const t = settingsTargetRef.current;
    if (t?.kind === "connections") {
      const next = settingsTargetAfterExit(t, settingsBeforeConnectionsRef.current);
      settingsTargetRef.current = next;
      setSettingsTarget(next);
    }
    setView(leavingSettingsView(t));
  }, []);

  const activeConnection = hostConnections.connections.find(
    (c) => c.id === hostConnections.active_id,
  );
  const daemonOffline =
    !!activeConnection &&
    (activeConnection.status === "offline" ||
      activeConnection.status === "disabled" ||
      activeConnection.status === "auth-failed" ||
      activeConnection.status === RATE_LIMITED);

  const sidebarSearchAvailable = !daemonOffline && view.kind !== "settings";
  const emptyRosterKey = workgroups.length > 0 ? "profiles" : adminOnNewProfile ? "roster" : "rosterMember";
  useEffect(() => {
    sidebarSearchAvailableRef.current = sidebarSearchAvailable;
    if (!sidebarSearchAvailable) setSidebarSearchOpen(false);
  }, [sidebarSearchAvailable]);

  const localActive = activeConnection?.kind === "local";
  const [localSeenOnline, setLocalSeenOnline] = useState(false);
  useEffect(() => {
    if (localActive && activeConnection?.status === "online") setLocalSeenOnline(true);
  }, [localActive, activeConnection?.status]);
  const localDaemon = useLocalDaemon({
    enabled: localActive && !localSeenOnline && activeConnection?.status === "offline",
    onStarted: onLocalDaemonStarted,
  });
  const showWelcome = localActive && daemonOffline
    && (localDaemon.phase !== "idle" || ["stopped", "absent", "unsupported"].includes(localDaemon.state));
  const retryLocal = useCallback(() => {
    setLocalSeenOnline(false);
    onRefreshHostConnectionStatus();
  }, [onRefreshHostConnectionStatus]);
  const [firstRunHint, setFirstRunHint] = useState(() => !firstRunHintSeen());
  const showFirstRunHint = firstRunHint && localActive && activeConnection?.status === "online" && view.kind !== "settings";
  const dismissFirstRunHint = useCallback(() => {
    markFirstRunHintSeen();
    setFirstRunHint(false);
  }, []);

  const activeStatus = activeConnection?.status;
  const connectionDisabled = activeStatus === "disabled";
  const connectionRateLimited = activeStatus === RATE_LIMITED;
  const switchBannerVisible = useDelayedFlag(
    connectionSwitching && !daemonOffline,
    300,
  );
  const connectionDisplayName =
    activeConnection?.kind === "remote"
      ? activeConnection?.name ?? "remote daemon"
      : "local daemon";

  // The local connection answers an outage with its welcome or the banner, never the switcher.
  const autoOpenConnectionSwitcher =
    hostConnections.connections.length > 0 &&
    (activeStatus === "auth-failed" ||
      connectionDisabled ||
      (activeStatus === "offline" && activeConnection?.kind !== "local"));

  const connectionLocked =
    autoOpenConnectionSwitcher &&
    !hostConnections.connections.some(
      (c) => c.kind === "remote" || c.status === "online",
    );

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

  const firstProfile = useMemo(() => firstRosterProfile(jumpTargets), [jumpTargets]);
  useEffect(() => {
    if (view.kind !== "landing" || !firstProfile || !(rosterAnswered || rosterSettled || daemonOffline)) return;
    setRewriteDraft(null);
    setView((v) => (v.kind === "landing" ? profileLandingView(firstProfile) : v));
  }, [view.kind, firstProfile, rosterAnswered, rosterSettled, daemonOffline]);

  const viewGenerationRef = useRef({ profile: null, generation: 0 });
  useEffect(() => {
    if (view.kind !== "profile") return;
    if (viewGenerationRef.current.profile !== view.profile) viewGenerationRef.current = { profile: view.profile, generation: rosterGeneration };
  }, [view.kind, view.profile, rosterGeneration]);
  useEffect(() => {
    if (!rosterAnswered || connectionSwitching || view.kind !== "profile") return;
    if (profiles.some((p) => p.name === view.profile)) return;
    if (rosterGeneration <= viewGenerationRef.current.generation) {
      reload();
      return;
    }
    setView((v) => (v.kind === "profile" && v.profile === view.profile ? LANDING_VIEW : v));
  }, [rosterAnswered, connectionSwitching, view.kind, view.profile, profiles, rosterGeneration, reload]);

  const lastProfileByConnectionRef = useRef({});
  useEffect(() => {
    if (view.kind === "profile" && view.profile) {
      lastProfileByConnectionRef.current[hostConnections.active_id ?? ""] = view.profile;
    }
  }, [view, hostConnections.active_id]);
  newSessionProfileRef.current = () =>
    newSessionProfile({
      view: viewRef.current,
      profiles: profilesRef.current,
      lastSeen: lastProfileByConnectionRef.current[hostConnectionsRef.current?.active_id ?? ""] ?? null,
      firstProfile,
    });

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
    searchOpen,
    onCycleTheme: () => cycleTheme(),
    activeProfileName,
    historyKind,
    onOpenSettings: adminOnOpenSettings,
    onCloseSettings: closeSettings,
    onToggleSearch,
    onToggleSidebarSearch: sidebarSearchAvailable ? onToggleSidebarSearch : null,
    sidebarSearchOpen,
    onNewProfile: adminOnNewProfile,
    onNewWorkgroup: adminOnNewWorkgroup,
    onNewSession: newSessionAvailable ? onNewSession : null,
    onRefreshThread:
      view.kind === "profile" || view.kind === "workgroup"
        ? onRefreshActiveThread
        : null,
    onToggleReadAloud: canReadAloud ? onToggleReadAloud : null,
    canReadAloud,
    readAloudActive,
    canRefreshThread: canRefreshProfileThread(view, sessionData),
    profilePaused: !!activeProfile?.paused,
    onToggleProfilePause:
      activeProfile && adminOnTogglePauseProfile ? onToggleActiveProfilePause : null,
    workgroupPaused: !!activeWorkgroup?.paused,
    onToggleWorkgroupPause: activeWorkgroup ? onToggleActiveWorkgroupPause : null,
    onBrowseTools: canManageProfileSurfaces ? onBrowseTools : null,
    onBrowseSkills: canManageProfileSurfaces ? onBrowseSkills : null,
    onBrowseMemory: canManageProfileSurfaces ? onBrowseMemory : null,
    onBrowseSchedule: canManageProfileSurfaces ? onBrowseSchedule : null,
    onOpenHistory,
    onToggleNotifications: canManageProfileSurfaces ? onOpenNotifications : null,
    onToggleActivity: onToggleActivityIfSupported,
    onOpenShortcuts: onToggleShortcuts,
  });

  const onPaletteOpenSession = useCallback((profile, sessionId) => {
    setRewriteDraft(null);
    setView({ kind: "profile", profile, sessionId });
  }, []);

  return (
    <div className={styles.app}>
      <Sidebar
        profiles={profiles}
        workgroups={workgroups}
        taskByWorkgroup={taskByWorkgroup}
        activityByWorkgroup={activityByWorkgroup}
        pendingProfiles={pendingProfiles}
        rosterState={rosterState}
        view={view}
        settingsTarget={settingsTarget}
        pinned={pinned}
        jumpHints={jumpHints}
        hostConnections={hostConnections}
        daemonOffline={daemonOffline}
        connectionSyncing={connectionSyncing}
        rosterAnswered={rosterAnswered}
        onNewSessionWith={onNewSessionWith}
        onOpenProfile={onOpenProfile}
        onOpenWorkgroup={onOpenWorkgroup}
        onViewAllWorkgroups={onViewAllWorkgroups}
        onOpenSettings={adminOnOpenSettings}
        onOpenPalette={onTogglePalette}
        onNewProfile={adminOnNewProfile}
        onNewWorkgroup={adminOnNewWorkgroup}
        onCloseSettings={closeSettings}
        onSetSettingsTarget={setSettingsTarget}
        onOpenSettingsTarget={adminOpenSettingsFor}
        onTogglePin={onTogglePin}
        onTogglePauseProfile={adminOnTogglePauseProfile}
        onSetHostConnection={onSetHostConnection}
        onAddHostConnection={onAddHostConnection}
        onForgetHostConnection={onForgetHostConnection}
        onRenameHostConnection={onRenameHostConnection}
        onRefreshHostConnectionStatus={onRefreshHostConnectionStatus}
        autoOpenConnectionSwitcher={autoOpenConnectionSwitcher}
        connectionLocked={connectionLocked}
        onOpenNotifications={canManageProfileSurfaces ? onOpenNotifications : null}
        notificationsUnread={canManageProfileSurfaces ? notificationsUnread : 0}
        searchOpen={sidebarSearchOpen}
        onCloseSearch={onCloseSidebarSearch}
        onOpenActivity={onToggleActivityIfSupported}
        activityNeedsYou={activityCounts.needsYou}
      />
      <main className={styles.main}>
          {daemonOffline && !showWelcome && (
            <Banner
              kind={connectionDisabled || connectionRateLimited ? "warning" : "danger"}
              pulsing={!connectionDisabled && !connectionRateLimited}
              action={connectionDisabled || connectionRateLimited ? null : "Retry"}
              onAction={connectionDisabled || connectionRateLimited ? null : localActive ? retryLocal : onRefreshHostConnectionStatus}
            >
              {connectionFailureMessage(activeConnection) ??
                (activeConnection?.kind === "remote"
                  ? `${activeConnection?.name ?? "Remote"} unreachable — check network / tunnel.`
                  : "alpi on this computer is not answering — reconnecting…")}
            </Banner>
          )}
          {showFirstRunHint && <FirstRunHint onDismiss={dismissFirstRunHint} />}
          {showWelcome ? (
            <Welcome
              localState={localDaemon.state}
              phase={localDaemon.phase}
              error={localDaemon.error}
              onStart={localDaemon.start}
              onCheckAgain={localDaemon.detect}
              onConnect={onAddHostConnection}
            />
          ) : view.kind === "settings" && canAdminEarly ? (
            <Settings
              profiles={profiles}
              workgroups={workgroups}
              target={settingsTarget}
              hostConnections={hostConnections}
              activeConnection={activeConnection}
              connectionSyncing={connectionSyncing}
              refreshTick={settingsRefreshTick}
              pinned={pinned}
              jumpHints={jumpHints}
              onTogglePin={onTogglePin}
              onSelectTarget={setSettingsTarget}
              onRefresh={onSettingsRefresh}
              onDeleteProfile={adminOnDeleteProfile}
              onOpenChat={closeSettings}
              onOpenConnections={openConnections}
              onCloseConnections={closeConnections}
              onSetHostConnection={onSetHostConnection}
              onAddHostConnection={onAddHostConnection}
              onForgetHostConnection={onForgetHostConnection}
              onRefreshHostConnectionStatus={onRefreshHostConnectionStatus}
            />
          ) : (
            <>
              {!daemonOffline && switchBannerVisible && (
                <Banner kind="info" pulsing>
                  {activeStatus === "online"
                    ? `Connected to ${connectionDisplayName} — syncing profiles…`
                    : `Connecting to ${connectionDisplayName}…`}
                </Banner>
              )}
              {view.kind === "workgroups" && (
                <WorkgroupsView
                  workgroups={workgroups}
                  profiles={profiles}
                  syncing={connectionSyncing}
                  taskByWorkgroup={taskByWorkgroup}
                  activityByWorkgroup={activityByWorkgroup}
                  onOpenWorkgroup={onOpenWorkgroup}
                  onNewWorkgroup={adminOnNewWorkgroup}
                />
              )}
              {view.kind === "workgroup" && activeWorkgroup && (
                <WorkgroupView
                  key={`${hostConnections.active_id}/${activeWorkgroup.profile}/${activeWorkgroup.id}`}
                  workgroup={activeWorkgroup}
                  profiles={profiles}
                  connectionId={hostConnections.active_id}
                  onReload={reload}
                  daemonOffline={daemonOffline}
                  onGone={onWorkgroupGone}
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
                  taskHistoryOpenTick={taskHistoryOpenTick}
                  refreshCommandTick={workgroupRefreshTick}
                  pauseCommandTick={workgroupPauseTick}
                />
              )}
              {view.kind === "landing" && !firstProfile && !rosterAnswered && rosterSettled && !connectionSwitching && !daemonOffline && (
                <LoadFailed label="profiles" onRetry={() => reload()} />
              )}
              {view.kind === "landing" && !firstProfile && rosterAnswered && !connectionSwitching && !daemonOffline && (
                <EmptyState
                  heading={EMPTY[emptyRosterKey].title}
                  subtitle={EMPTY[emptyRosterKey].hint}
                >
                  {adminOnNewProfile && (
                    <Button variant="primary" onClick={adminOnNewProfile}>New profile</Button>
                  )}
                </EmptyState>
              )}
              {view.kind === "profile" && (
                <ChatPane
                  view={view}
                  profiles={profiles}
                  activeProfile={activeProfile}
                  connectionId={hostConnections.active_id}
                  sessionData={sessionData}
                  sessionSync={sessionSync}
                  loadError={sessionLoadFailure}
                  onRetryLoad={() => setSessionRetryTick((t) => t + 1)}
                  daemonOffline={daemonOffline}
                  pendingTurn={pendingTurnForCurrentView}
                  inlineApprovals={approvalSplit.inline}
                  inlineClarifications={clarificationSplit.inline}
                  onApprovalResolved={approval.resolve}
                  onClarificationResolved={clarification.resolve}
                  onSend={onSend}
                  onCancel={onCancelTurn}
                  onConfigureProfile={canAdminEarly ? (p) => {
                    setSettingsTarget({ kind: "profile", id: p.name });
                    setView({ kind: "settings" });
                  } : null}
                  onTogglePauseProfile={adminOnTogglePauseProfile}
                  onRewriteMessage={onRewriteMessage}
                  onRetryMessage={onRetryMessage}
                  rewriteDraft={rewriteDraft}
                  onRewriteDraftApplied={() => {
                    setRewriteDraft((prev) =>
                      prev ? { ...prev, consumed: true } : prev,
                    );
                  }}
                  pendingAttachment={pendingAttachment}
                  onPendingAttachmentApplied={() => {
                    setPendingAttachment((prev) =>
                      prev ? { ...prev, consumed: true } : prev,
                    );
                  }}
                  onOpenSkills={canManageProfileSurfaces ? onBrowseSkills : null}
                  onOpenMemory={canManageProfileSurfaces ? onBrowseMemory : null}
                  onOpenTools={canManageProfileSurfaces ? onBrowseTools : null}
                  onOpenSchedule={canManageProfileSurfaces ? onBrowseSchedule : null}
                  canManageProfileSurfaces={canManageProfileSurfaces}
                  onRefreshSession={onRefreshSession}
                  onNewSession={onNewSessionForCurrentProfile}
                  sessionsOpenTick={sessionsDropdownOpenTick}
                  readAloudTick={readAloudTick}
                  onChangeSession={onChangeSession}
                  searchOpen={searchOpen}
                  onCloseSearch={onCloseSearch}
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
        jumpHints={jumpHints}
        connectionId={hostConnections.active_id}
        onOpenProfile={onOpenProfile}
        onOpenWorkgroup={onOpenWorkgroup}
        onOpenSession={onPaletteOpenSession}
      />
      <ShortcutsSheet open={shortcutsOpen} onClose={onCloseShortcuts} />
      <ActivityPanel
        open={activityOpen && activitySupported}
        onClose={onCloseActivity}
        activity={activity}
        accentByProfile={accentByProfile}
        foldByProfile={foldByProfile}
        onReview={onReviewActivity}
        onOpenSession={(profile, sessionId) => {
          setRewriteDraft(null);
          setView({ kind: "profile", profile, sessionId: sessionId || null });
        }}
        onOpenWorkgroup={(profile, id) => setView({ kind: "workgroup", profile, id })}
        onOpenProfile={(name) => {
          const p = profilesRef.current.find((x) => x.name === name);
          if (p) onOpenProfile(p);
        }}
      />
      <ProfilePanels
        key={profileSurfaceKey("panels", hostConnections.active_id, activeProfileName)}
        section={canManageProfileSurfaces ? browse : null}
        onSection={(id) => { setScheduleJob(null); setBrowse(id); }}
        onClose={onCloseBrowse}
        owner={panelOwner}
        profile={activeProfileName}
        connectionId={hostConnections.active_id}
        canEdit={canAdminEarly}
        openJob={scheduleJob}
        guardRef={panelGuardRef}
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
            markWorkgroupRead(hostConnections.active_id, hubName, wgId);
            setSettingsTarget({ kind: "workgroup", id: wgId, profile: hubName });
            setView({ kind: "settings" });
          }
        }}
      />
      <ApprovalModal requests={approvalSplit.modal} onResolved={approval.resolve} profiles={profiles} />
      <ClarificationModal requests={clarificationSplit.modal} onResolved={clarification.resolve} />
      {notificationsOpen && canManageProfileSurfaces && <NotificationsModal
        open={notificationsOpen}
        onClose={onCloseNotifications}
        connections={hostConnections.connections}
        activeConnectionId={hostConnections.active_id}
        selectedId={notificationsTarget?.id}
        selectedProfile={notificationsTarget?.profile}
        selectedConnectionId={notificationsTarget?.connectionId}
        onOpenChat={(profile, sessionId, connId) => {
          if (!panelsMayLeave()) return;
          if (viewRef.current?.kind === "settings" && hasDirtySettings()) {
            window.notify?.("Save or discard your settings changes first", { variant: "info" });
            return;
          }
          if (connId && connId !== hostConnections.active_id) onSetHostConnection(connId);
          setView({ kind: "profile", profile, sessionId: sessionId || null });
        }}
        onOpenJob={canManageProfileSurfaces ? (profile, jobId) => {
          if (!panelsMayLeave()) return;
          if (activeProfileName !== profile) {
            if (viewRef.current?.kind === "settings" && hasDirtySettings()) {
              window.notify?.("Save or discard your settings changes first", { variant: "info" });
              return;
            }
            const target = profiles.find((p) => p.name === profile);
            setView(target ? profileLandingView(target) : { kind: "profile", profile, sessionId: null });
          }
          setScheduleJob({ id: jobId });
          setBrowse("schedule");
        } : null}
        onSendToChat={(profile, connId, attachment) => {
          if (!panelsMayLeave()) return;
          if (viewRef.current?.kind === "settings" && hasDirtySettings()) {
            window.notify?.("Save or discard your settings changes first", { variant: "info" });
            return;
          }
          setPendingAttachment({ profile, connectionId: connId ?? null, attachment, consumed: false });
          if (connId && connId !== hostConnections.active_id) onSetHostConnection(connId);
          detachNewChatTurns(connId ?? hostConnections.active_id ?? null, profile);
          setRewriteDraft(null);
          setView({ kind: "profile", profile, sessionId: null });
        }}
      />}
    </div>
  );
}
