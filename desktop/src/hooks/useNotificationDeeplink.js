import { useEffect, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { getCurrentWebviewWindow } from "@tauri-apps/api/webviewWindow";
import {
  isPermissionGranted,
  requestPermission,
} from "@tauri-apps/plugin-notification";
import { safeUnlisten } from "../lib/tauri-listen.js";

const DEEPLINK_TTL_MS = 30_000;

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
  if (kind !== "chat" && kind !== "profile" && kind !== "workgroup") return null;
  return id;
}

export function useNotificationDeeplink({
  setView,
  setSettingsTarget,
  openNotifications,
  onSwitchConnection,
  activeConnectionId,
}) {
  const pendingRef = useRef(null);
  const openNotificationsRef = useRef(openNotifications);
  useEffect(() => { openNotificationsRef.current = openNotifications; }, [openNotifications]);
  const onSwitchConnectionRef = useRef(onSwitchConnection);
  useEffect(() => { onSwitchConnectionRef.current = onSwitchConnection; }, [onSwitchConnection]);
  const activeConnectionIdRef = useRef(activeConnectionId);
  useEffect(() => { activeConnectionIdRef.current = activeConnectionId; }, [activeConnectionId]);

  useEffect(() => {
    let unlistenFired = null;
    let unlistenFocus = null;
    let cancelled = false;

    const consume = () => {
      const pending = pendingRef.current;
      if (!pending) return;
      if (Date.now() - pending.firedAt > DEEPLINK_TTL_MS) {
        pendingRef.current = null;
        return;
      }
      pendingRef.current = null;
      const target = connectionToSwitch(pending.deeplink, activeConnectionIdRef.current);
      if (target) onSwitchConnectionRef.current?.(target);
      const action = resolveDeeplink(pending.deeplink);
      if (!action) return;
      if (action.settingsTarget !== undefined) {
        setSettingsTarget(action.settingsTarget);
      }
      if (action.view) setView(action.view);
      if (action.notifications) openNotificationsRef.current?.(action.notifications);
    };

    (async () => {
      try {
        if (!(await isPermissionGranted())) await requestPermission();
      } catch {
        // unsigned dev bundle: silently degrade.
      }
      if (cancelled) return;
      try {
        unlistenFired = await listen("notification-fired", (ev) => {
          const payload = ev?.payload || {};
          pendingRef.current = {
            firedAt: Number(payload.fired_at) || Date.now(),
            deeplink: payload.deeplink || {},
          };
        });
      } catch { /* tauri race */ }
      if (cancelled) {
        safeUnlisten(unlistenFired);
        return;
      }
      try {
        const win = getCurrentWebviewWindow();
        unlistenFocus = await win.onFocusChanged(({ payload: focused }) => {
          if (focused) consume();
        });
      } catch { /* tauri race */ }
    })();

    return () => {
      cancelled = true;
      safeUnlisten(unlistenFired);
      safeUnlisten(unlistenFocus);
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
