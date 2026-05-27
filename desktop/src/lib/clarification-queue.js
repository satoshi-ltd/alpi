// Pure helpers for the clarification queue in App.jsx. Mirror of approval-queue.js — same dedupe + deadline math, different payload shape (question/choices instead of command/severity).

export function deadlineFor(req) {
  if (!req || typeof req.timeout_s !== "number") return null;
  const window = Math.max(0, req.timeout_s * 1000);
  if (typeof req.ts === "number") return req.ts * 1000 + window;
  return Date.now() + window;
}

export function normalizeRequest(req) {
  if (!req || !req.request_id) return null;
  const choices = Array.isArray(req.choices) ? req.choices : [];
  const multi = !!req.multi;
  return {
    request_id: req.request_id,
    profile: req.profile || null,
    question: req.question || "",
    choices: choices
      .filter((c) => c && typeof c.label === "string" && c.label.trim())
      .map((c) => ({
        label: String(c.label),
        description: typeof c.description === "string" ? c.description : "",
      })),
    allow_other: multi ? false : !!req.allow_other,
    multi,
    deadline: deadlineFor(req),
  };
}

export function enqueueRequest(queue, req) {
  const entry = normalizeRequest(req);
  if (!entry) return queue;
  if (entry.choices.length < 2) return queue;
  if (queue.some((r) => r.request_id === entry.request_id)) return queue;
  return [...queue, entry];
}
