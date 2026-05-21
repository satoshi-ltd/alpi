// Pure helpers for the approval queue in App.jsx. Split out so the dedupe + deadline math can be unit-tested without rendering the modal tree.

export function deadlineFor(req) {
  if (!req || typeof req.timeout_s !== "number") return null;
  const window = Math.max(0, req.timeout_s * 1000);
  if (typeof req.ts === "number") return req.ts * 1000 + window;
  return Date.now() + window;
}

export function normalizeRequest(req) {
  if (!req || !req.request_id) return null;
  return {
    request_id: req.request_id,
    command: req.command || "",
    severity: req.severity || "caution",
    pattern: req.pattern || "",
    profile: req.profile || null,
    deadline: deadlineFor(req),
  };
}

export function enqueueRequest(queue, req) {
  const entry = normalizeRequest(req);
  if (!entry) return queue;
  if (queue.some((r) => r.request_id === entry.request_id)) return queue;
  return [...queue, entry];
}
