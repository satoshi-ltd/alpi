// Maps host.events.emit() kinds onto applyChange's fs-change vocabulary.
// Forward-compatible: unknown kinds return null. Pure function — easy to unit-test.

// "drop": foreign daemon. "replay": reconnect backfill — refresh once, never fan out per event.
export function classifyDaemonPayload(payload, activeConnectionId) {
  if (!payload || typeof payload !== "object") return "drop";
  if (payload.connection_id && payload.connection_id !== activeConnectionId) {
    return "drop";
  }
  if (payload.replay) return "replay";
  return "live";
}

export function isActiveWorkgroupView(view, ev) {
  return (
    view?.kind === "workgroup" &&
    view.id === ev?.wg_id &&
    view.profile === ev?.profile
  );
}

export function fromDaemonFrame(frame) {
  if (!frame || typeof frame !== "object") return null;
  const event = frame.event;
  const data = frame.data ?? {};
  if (!event || typeof event !== "string") return null;
  if (event === "session_changed") {
    if (!data.profile) return null;
    return {
      kind: "session",
      profile: data.profile,
      session_id: data.session_id ?? data.id ?? null,
    };
  }
  if (
    event === "wg.post" ||
    event === "wg.done" ||
    event === "wg.task" ||
    event === "wg.skip"
  ) {
    if (!data.profile || !data.wg_id) return null;
    return { kind: "workgroup_transcript", profile: data.profile, wg_id: data.wg_id };
  }
  if (event === "workgroup_changed" || event === "workgroup_meta" || event === "workgroup_members") {
    return { kind: "workgroup_meta" };
  }
  if (event === "approval.request" || event === "approval.resolved") {
    // App.jsx handles these in-place (queue mutations); applyChange is for fs invalidations.
    return null;
  }
  if (event === "peer.pairing_request" || event === "peers_changed") return { kind: "peers" };
  if (event === "subscriptions_changed") return { kind: "subscriptions" };
  if (
    event === "schedule.done" ||
    event === "schedule.failed" ||
    event === "schedule.changed" ||
    event === "profile_changed" ||
    event === "config_changed" ||
    event === "skills_changed" ||
    event === "memory_changed" ||
    event === "gateway_changed" ||
    event === "budget.threshold"
  ) {
    return { kind: "config" };
  }
  return null;
}
