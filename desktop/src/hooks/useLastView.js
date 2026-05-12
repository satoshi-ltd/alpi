import { useEffect, useRef } from "react";

const KEY_PREFIX = "alf:last-view:v1:";

// Persist the last "real" view (profile/workgroup) per connection so a
// reopen lands the user back on the chat they were using. Settings and
// empty views are intentionally not persisted — they're transient.
export function useLastView({
  connectionId,
  view,
  setView,
  profiles,
  workgroups,
}) {
  const restoredRef = useRef(false);

  useEffect(() => {
    if (!connectionId) return;
    if (view.kind !== "profile" && view.kind !== "workgroup") return;
    try {
      localStorage.setItem(
        KEY_PREFIX + connectionId,
        JSON.stringify(view),
      );
    } catch {}
  }, [connectionId, view]);

  useEffect(() => {
    if (!connectionId) return;
    if (restoredRef.current) return;
    if (view.kind !== "empty") {
      restoredRef.current = true;
      return;
    }
    if (profiles.length === 0 && workgroups.length === 0) return;

    let saved = null;
    try {
      const raw = localStorage.getItem(KEY_PREFIX + connectionId);
      if (raw) saved = JSON.parse(raw);
    } catch {}

    restoredRef.current = true;
    if (!saved) return;

    if (saved.kind === "profile" && saved.profile) {
      const exists = profiles.some((p) => p.name === saved.profile);
      if (exists) setView(saved);
      return;
    }
    if (saved.kind === "workgroup" && saved.id) {
      const exists = workgroups.some(
        (w) => w.id === saved.id && w.profile === saved.profile,
      );
      if (exists) setView(saved);
    }
  }, [connectionId, view.kind, profiles, workgroups, setView]);

  useEffect(() => {
    restoredRef.current = false;
  }, [connectionId]);
}
