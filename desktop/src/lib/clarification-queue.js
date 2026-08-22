import { deadlineFor } from "./approval-queue.js";

export { deadlineFor };

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
