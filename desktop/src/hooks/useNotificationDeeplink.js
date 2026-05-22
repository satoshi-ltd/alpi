import { useEffect, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { getCurrentWebviewWindow } from "@tauri-apps/api/webviewWindow";
import {
  isPermissionGranted,
  requestPermission,
} from "@tauri-apps/plugin-notification";

const DEEPLINK_TTL_MS = 30_000;

export function resolveDeeplink(deeplink) {
  const { kind, profile, id } = deeplink || {};
  if (kind === "chat" && profile) {
    return { view: { kind: "profile", profile, sessionId: id || null } };
  }
  if (kind === "profile" && profile) {
    return { view: { kind: "profile", profile, sessionId: null } };
  }
  if (kind === "workgroup" && profile && id) {
    return { view: { kind: "workgroup", profile, id } };
  }
  if (kind === "settings") {
    return {
      settingsTarget: profile ? { kind: "profile", id: profile } : null,
      view: { kind: "settings" },
    };
  }
  return null;
}

export function useNotificationDeeplink({ setView, setSettingsTarget }) {
  const pendingRef = useRef(null);

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
      const action = resolveDeeplink(pending.deeplink);
      if (!action) return;
      if (action.settingsTarget !== undefined) {
        setSettingsTarget(action.settingsTarget);
      }
      if (action.view) setView(action.view);
    };

    (async () => {
      try {
        if (!(await isPermissionGranted())) await requestPermission();
      } catch {
        // unsigned dev bundle: silently degrade.
      }
      if (cancelled) return;
      unlistenFired = await listen("notification-fired", (ev) => {
        const payload = ev?.payload || {};
        pendingRef.current = {
          firedAt: Number(payload.fired_at) || Date.now(),
          deeplink: payload.deeplink || {},
        };
      });
      if (cancelled) {
        unlistenFired?.();
        return;
      }
      const win = getCurrentWebviewWindow();
      unlistenFocus = await win.onFocusChanged(({ payload: focused }) => {
        if (focused) consume();
      });
    })();

    return () => {
      cancelled = true;
      unlistenFired?.();
      unlistenFocus?.();
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
