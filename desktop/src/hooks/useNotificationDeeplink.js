import { useEffect, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import {
  isPermissionGranted,
  requestPermission,
} from "@tauri-apps/plugin-notification";
import { hasDirtySettings } from "../lib/settingsDirty.js";
import { safeUnlisten } from "../lib/tauri-listen.js";

const DEFER_MS = 15000;

export function resolveDeeplink(deeplink) {
  const { kind, profile, id, connection_id: connectionId } = deeplink || {};
  if (kind === "chat" && profile) {
    return { view: { kind: "profile", profile, sessionId: id || null } };
  }
  if (kind === "profile" && profile) {
    return { view: { kind: "profile", profile, sessionId: null } };
  }
  if (kind === "workgroup" && profile && id) {
    return { view: { kind: "workgroup", profile, id } };
  }
  if (kind === "output" && profile && id) {
    // No view swap — leave whatever the user is on. The opened modal owns selection.
    const target = { profile, id };
    if (connectionId) target.connectionId = connectionId;
    return { notifications: target };
  }
  if ((kind === "approval" || kind === "clarification") && id) {
    return { request: { kind, id, profile: profile || null } };
  }
  if (kind === "settings" && id === "schedules" && profile) {
    return { schedule: { profile } };
  }
  if (kind === "settings") {
    // Convention: undefined settingsTarget means "keep current"; null would crash settingsTarget.kind in App.jsx.
    const action = { view: { kind: "settings" } };
    if (profile) action.settingsTarget = { kind: "profile", id: profile };
    return action;
  }
  return null;
}

export function connectionToSwitch(deeplink, activeConnectionId) {
  const id = deeplink?.connection_id;
  if (typeof id !== "string" || !id) return null;
  if (id === activeConnectionId) return null;
  const kind = deeplink?.kind;
  const scoped = kind === "chat" || kind === "profile" || kind === "workgroup" || kind === "approval" || kind === "clarification";
  if (!scoped && !(kind === "settings" && deeplink?.id === "schedules")) return null;
  return id;
}

export function useNotificationDeeplink({
  setView,
  setSettingsTarget,
  openNotifications,
  onSwitchConnection,
  activeConnectionId,
  focusRequest,
  openSchedule,
  canOpenSchedule,
}) {
  const openNotificationsRef = useRef(openNotifications);
  useEffect(() => { openNotificationsRef.current = openNotifications; }, [openNotifications]);
  const onSwitchConnectionRef = useRef(onSwitchConnection);
  useEffect(() => { onSwitchConnectionRef.current = onSwitchConnection; }, [onSwitchConnection]);
  const focusRequestRef = useRef(focusRequest);
  useEffect(() => { focusRequestRef.current = focusRequest; }, [focusRequest]);
  const openScheduleRef = useRef(openSchedule);
  useEffect(() => { openScheduleRef.current = openSchedule; }, [openSchedule]);
  const canOpenScheduleRef = useRef(canOpenSchedule);
  useEffect(() => { canOpenScheduleRef.current = canOpenSchedule; }, [canOpenSchedule]);
  const deferredRef = useRef(null);
  const activeConnectionIdRef = useRef(activeConnectionId);
  useEffect(() => { activeConnectionIdRef.current = activeConnectionId; }, [activeConnectionId]);

  const applyAfterSwitch = (action) => {
    if (action.request) focusRequestRef.current?.(action.request);
    if (action.schedule) openScheduleRef.current?.(action.schedule.profile);
  };
  useEffect(() => {
    const deferred = deferredRef.current;
    if (!deferred || deferred.connection !== activeConnectionId) return;
    deferredRef.current = null;
    if (Date.now() - deferred.at <= DEFER_MS) applyAfterSwitch(deferred.action);
  }, [activeConnectionId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    let unlistenActivated = null;
    let cancelled = false;

    const consume = (deeplink) => {
      const action = resolveDeeplink(deeplink);
      if (!action) return;
      if ((action.view || action.schedule) && hasDirtySettings()) {
        window.notify?.("Save or discard your settings changes first", { variant: "info" });
        return;
      }
      if (action.schedule && !canOpenScheduleRef.current?.(deeplink?.connection_id || activeConnectionIdRef.current)) return;
      const target = connectionToSwitch(deeplink, activeConnectionIdRef.current);
      const deferred = target && (action.request || action.schedule) ? { connection: target, action, at: Date.now() } : null;
      if (deferred) deferredRef.current = deferred;
      if (target) {
        Promise.resolve(onSwitchConnectionRef.current?.(target)).catch(() => {
          if (deferredRef.current === deferred) deferredRef.current = null;
        });
      }
      if (action.settingsTarget !== undefined) {
        setSettingsTarget(action.settingsTarget);
      }
      if (action.view) setView(action.view);
      if (action.notifications) openNotificationsRef.current?.(action.notifications);
      if (deferred) return;
      applyAfterSwitch(action);
    };

    (async () => {
      try {
        if (!(await isPermissionGranted())) await requestPermission();
      } catch {
        // unsigned dev bundle: silently degrade.
      }
      if (cancelled) return;
      try {
        unlistenActivated = await listen("notification-activated", (ev) => {
          consume(ev?.payload?.deeplink || {});
        });
      } catch { /* tauri race */ }
      if (cancelled) {
        safeUnlisten(unlistenActivated);
      }
    })();

    return () => {
      cancelled = true;
      safeUnlisten(unlistenActivated);
    };
  }, [setView, setSettingsTarget]);
}

export function useActiveViewPing(view) {
  useEffect(() => {
    let kind = null;
    let id = null;
    if (view?.kind === "profile" && view.sessionId) {
      kind = "chat";
      id = view.sessionId;
    } else if (view?.kind === "profile" && view.profile) {
      kind = "chat-new";
      id = view.profile;
    } else if (view?.kind === "workgroup") {
      kind = "workgroup";
      id = view.id;
    } else if (view?.kind === "settings") {
      kind = "settings";
      id = "settings";
    }
    invoke("set_active_view", { kind, id }).catch(() => {});
  }, [view?.kind, view?.profile, view?.sessionId, view?.id]);
}
