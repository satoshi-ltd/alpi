const RATE_LIMITED = "Too many authentication attempts from this IP. Wait a minute and try again.";
const TOO_MANY = "This device has too many open connections to the daemon. Wait a few seconds and try again.";
const CLOSED = "The connection to the daemon closed. Reconnecting.";
const UNREACHABLE = "Cannot reach the daemon.";

const closedBy = (reason) => `websocket closed by daemon \\(${reason}\\)`;

const MAX_CHARS = 2000;

const RULES = [
  [closedBy("1013 auth-rate-limited"), RATE_LIMITED],
  [`too-many-connections|${closedBy("1013 Device connection limit reached")}`, TOO_MANY],
  ["too-many-requests", "Too many requests at once. Try again in a moment."],
  [closedBy("1013 WebSocket capacity reached"), "The daemon is at capacity. Try again in a moment."],
  [closedBy("1008 Authorization changed"), "This device's permissions changed. Reconnecting."],
  [`${closedBy("1008 Device authorization revoked")}|connection is revoked: \\S+`,
    "This device is no longer authorised. Pair it again."],
  ["forbidden", "This device is not allowed to do that.", true],
  ["method-not-found", "The daemon is older than this app and does not support that yet. Update alpi."],
  ["websocket closed by daemon(?: \\([^)]*\\))?|connection closed before (?:response|done)|connection to \\S+ went stale", CLOSED],
  ["read-timeout(?::.*)?|request timed out after \\d+ms", "The daemon took too long to answer."],
  ["connect /\\S*host\\.sock: .*", "The local alpi daemon is not running."],
  ["connect ws://\\S+: .*|connection failed to \\S+|stream open timed out after \\d+ms", UNREACHABLE],
  ["send failed: .*|websocket (?:read|write|handshake)\\b[^:]*: .*", "The connection to the daemon failed."],
  ["invalid JSON in (?:response|frame)", "The daemon sent something this app could not read."],
].map(([body, sentence, keepDetail]) => [
  new RegExp(`(^|: )(?:alp -?\\d+: )?(?:${body})(?: — (.*))?$`),
  sentence,
  keepDetail === true,
]);

export function plainError(text) {
  const raw = String(text ?? "");
  if (raw.length > MAX_CHARS) return raw;
  for (const [pattern, sentence, keepDetail] of RULES) {
    if (pattern.test(raw)) {
      return raw.replace(pattern, (_match, lead, detail) =>
        lead + sentence + (keepDetail && detail ? ` (${detail})` : ""));
    }
  }
  return raw;
}
