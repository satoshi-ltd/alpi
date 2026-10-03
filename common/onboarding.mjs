export const PAIRING_STEPS = ["read", "reach", "sign-in"];

export function pairingStepLabel(step, host) {
  if (step === "read") return "Link read";
  if (step === "reach") return `Reaching ${host || "the host"}`;
  return "Signing in";
}

export const LINK_SOURCES = [
  "In the alpi desktop app: Settings → Connections → New connection.",
  "In a terminal on the host: alpi setup → Connections → New connection.",
];

export const INSTALL_COMMANDS = ["uv tool install alpi-agent", "alpi setup"];

export const START_COMMAND = "alpi daemon start";

export function memberEmptyCopy(deviceName) {
  return {
    title: "Nothing shared with this device yet",
    hint: `Ask the host admin to share a profile with ${deviceName ? deviceName : "this device"}.`,
  };
}

export function pairedRoleLine(role, sharedCount) {
  if (role === "member") {
    const n = Number.isFinite(sharedCount) ? sharedCount : 0;
    return n === 0 ? "member · nothing shared yet" : `member · ${n} ${n === 1 ? "profile" : "profiles"} shared`;
  }
  return "admin · all profiles";
}

const FAILURES = {
  unreachable: {
    title: (host) => `Can't reach ${host || "the host"}`,
    hint: "Check that the host is on and reachable from here, then try again.",
    action: "Try again",
    keepLink: true,
  },
  "link-used": {
    title: () => "This link was already used or has expired",
    hint: "Make a new one on the host and paste it here.",
    action: "Use a new link",
    keepLink: false,
  },
  disabled: {
    title: () => "The host disabled this connection",
    hint: "Ask the host admin to enable it in Settings → Connections.",
    action: "Try again",
    keepLink: true,
  },
  "too-old": {
    title: () => "alpi on the host is too old",
    hint: "Update alpi on the host, then try again.",
    action: "Try again",
    keepLink: true,
  },
  "rate-limited": {
    title: () => "Too many attempts",
    hint: "Wait a minute, then try again.",
    action: "Try again",
    keepLink: true,
  },
  invalid: {
    title: () => "That is not an alpi link",
    hint: "Paste the whole alpi:// link the host made for this device.",
    action: "Use a new link",
    keepLink: false,
  },
  unknown: {
    title: () => "Pairing failed",
    hint: "Try again, or make a new link on the host.",
    action: "Try again",
    keepLink: true,
  },
};

const UNREACHABLE = /unreachable|timed out|timeout|refused|network|connection (closed|failed|reset)|went stale|send failed|cannot resolve host|handshake|websocket closed|enotfound|econn/;

export function pairingFailureKind(statusOrError) {
  const text = String(statusOrError?.message ?? statusOrError ?? "").toLowerCase();
  if (statusOrError?.code === -32011 || /pairing-(used|expired|invalid)|-32011/.test(text)) return "link-used";
  if (text === "disabled" || /connection-disabled/.test(text)) return "disabled";
  if (text === "rate-limited" || /rate-limited|too-many|too many/.test(text)) return "rate-limited";
  if (statusOrError?.transport === true || text === "offline" || UNREACHABLE.test(text)) return "unreachable";
  if (text === "auth-failed" || /auth-failed|token rejected|invalid token|pairing code (expired|already used|invalid)|unknown pairing/.test(text)) return "link-used";
  if (text === "too-old" || /too old|method-not-found|-32601/.test(text)) return "too-old";
  if (/not an alpi|invalid link|unsupported link|pairing payload|parse/.test(text)) return "invalid";
  return "unknown";
}

export function pairingFailure(kind, host) {
  const entry = FAILURES[kind] ?? FAILURES.unknown;
  return { kind: FAILURES[kind] ? kind : "unknown", title: entry.title(host), hint: entry.hint, action: entry.action, keepLink: entry.keepLink };
}

export function pairingLinkHost(link) {
  const text = String(link ?? "").trim();
  if (!text.startsWith("alpi://")) return null;
  const query = text.slice(text.indexOf("?") + 1);
  const params = new URLSearchParams(query);
  const name = params.get("name") || params.get("host");
  if (name) return name;
  try {
    return new URL(params.get("url") ?? "").hostname || null;
  } catch {
    return null;
  }
}

export function failedStep(kind) {
  if (kind === "invalid") return "read";
  if (kind === "unreachable" || kind === "rate-limited") return "reach";
  return "sign-in";
}
