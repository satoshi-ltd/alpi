const KIND = {
  active: "active",
  running: "active",
  ok: "active",
  paused: "paused",
  off: "paused",
  attention: "attention",
  inactive: "attention",
  lint: "attention",
  over: "attention",
  failed: "failed",
  error: "failed",
  invalid: "failed",
};

export const STATUS_WORDS = ["active", "paused", "attention", "failed"];

export function statusKind(word) {
  return KIND[word] ?? "paused";
}

export function statusDot(word) {
  const kind = statusKind(word);
  return kind === "active" ? "filled" : kind === "paused" ? "hollow" : "red";
}
