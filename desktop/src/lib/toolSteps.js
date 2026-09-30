const FAMILY_BY_NAME = {
  read_file: "file",
  write_file: "file",
  edit_file: "file",
  edit: "file",
  delete_file: "file",
  list_dir: "file",
  attach_file: "file",
  read_image: "file",
  workgroup_file: "file",
  terminal: "terminal",
  shell: "terminal",
  run: "terminal",
  bash: "terminal",
  web_fetch: "globe",
  web_search: "globe",
  web_extract: "globe",
  browser: "globe",
  research: "globe",
  grep: "search",
  glob: "search",
  search: "search",
  find: "search",
  session_search: "search",
  workgroup_search: "search",
  recall_sessions: "search",
  peer: "link",
  alp: "link",
  send_message: "link",
  notify: "link",
  email: "link",
  delegate: "link",
  workgroup_post: "link",
  memory: "brain",
};

export function toolIcon(name) {
  const n = String(name || "").toLowerCase();
  if (FAMILY_BY_NAME[n]) return FAMILY_BY_NAME[n];
  if (/(^|_)(file|dir)s?($|_)/.test(n)) return "file";
  if (/(^|_)(shell|terminal)($|_)/.test(n)) return "terminal";
  if (/^web_|browser/.test(n)) return "globe";
  if (/(^|_)(grep|search|find)($|_)/.test(n)) return "search";
  if (/(^|_)(peer|alp)($|_)/.test(n)) return "link";
  if (/memory/.test(n)) return "brain";
  return "cpu";
}

function clip(value, max) {
  const s = String(value ?? "").replace(/\s+/g, " ").trim();
  return s.length > max ? `${s.slice(0, max - 1)}…` : s;
}

const PRIMARY_ARG = ["command", "cmd", "path", "file_path", "url", "pattern", "query", "q", "question", "peer_id", "channel", "title", "name"];

export function argsPreview(args) {
  if (!args || typeof args !== "object") return "";
  return Object.entries(args).slice(0, 2).map(([k, v]) => {
    const raw = typeof v === "string" ? v : JSON.stringify(v);
    return `${k}=${clip(raw, 60)}`;
  }).join(" ");
}

export function toolSummary(tool) {
  if (tool?.preview) return clip(tool.preview, 120);
  const args = tool?.args;
  if (!args || typeof args !== "object") return "";
  const action = typeof args.action === "string" ? args.action : "";
  const key = PRIMARY_ARG.find((k) => typeof args[k] === "string" && args[k].trim());
  if (key) return clip(action && key !== "command" ? `${action} · ${args[key]}` : args[key], 120);
  if (action) return clip([action, args.target].filter((v) => typeof v === "string" && v).join(" · "), 120);
  return argsPreview(args);
}

export function fmtToolDuration(seconds) {
  if (typeof seconds !== "number" || !Number.isFinite(seconds) || seconds < 0) return "";
  if (seconds < 10) return `${(Math.round(seconds * 10) / 10).toFixed(1)}s`;
  const n = Math.round(seconds);
  if (n < 60) return `${n}s`;
  const m = Math.floor(n / 60);
  const r = n % 60;
  return r ? `${m}m ${r}s` : `${m}m`;
}

export function prettyArgs(args) {
  if (args == null) return "";
  if (typeof args === "string") {
    try {
      return JSON.stringify(JSON.parse(args), null, 2);
    } catch {
      return args;
    }
  }
  try {
    return JSON.stringify(args, null, 2);
  } catch {
    return String(args);
  }
}

const STORED_RESULT_CAP = 400;
const LIVE_OUTPUT_CAP = 4000;

export function toolResult(tool) {
  const live = typeof tool?.output === "string" && tool.output ? tool.output : null;
  const text = live ?? (typeof tool?.result === "string" ? tool.result : "");
  if (!text) return null;
  const cap = live != null ? LIVE_OUTPUT_CAP : STORED_RESULT_CAP;
  const excerpt = text.length >= cap && text.endsWith("…");
  return { text, excerpt };
}
