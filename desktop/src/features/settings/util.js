export const ACCENT_PALETTE = [
  "#b8954a", // gold (default · alpi)
  "#d97757", // terracotta
  "#c14545", // brick
  "#c14580", // magenta
  "#9d4dc6", // purple
  "#6a6dd6", // indigo
  "#3d7ea6", // denim
  "#2f8e9e", // teal
  "#2f7d6e", // pine
  "#3fb37a", // forest (workgroup default)
  "#8a7a4a", // olive
  "#6c7480", // slate
];

export const ACCENT_DEFAULT_PROFILE = "#b8954a";
export const ACCENT_DEFAULT_WORKGROUP = "#3fb37a";

export const HEX_RE = /^#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$/;

export const FIELD_KEYS = {
  bio: "public_bio",
  workspace: "workspace",
  model: "model",
  accent: "tui.accent",
  reasoningEffort: "model_reasoning.effort",
};

export const SUBSYSTEMS = ["schedule", "alp", "workgroups"];

export const SUBSYSTEM_DESC = {
  schedule: "Cron jobs",
  alp: "Inter-machine peer protocol",
  workgroups: "Workgroup background poller",
};

export const STORAGE_SCOPE = {
  sessions: "chat transcripts",
  skills: "user-created skills (scripts, references, state)",
  memories: "USER.md, MEMORY.md, AGENT.md + backups + promotion queue",
  rag: "workspace embeddings (sqlite-vec store)",
  outputs: "notifications inbox",
  audio: "TTS output + inbound voice notes",
  logs: "schedule, agent, approval",
  schedule: "stdout/stderr of past jobs",
  workgroups: "encrypted transcripts + turn telemetry",
  mentions: "@-mention threads from ALP peers",
};

export const PAID_PROVIDERS = [
  { id: "anthropic", env: "ANTHROPIC_API_KEY", label: "Anthropic" },
  { id: "openai", env: "OPENAI_API_KEY", label: "OpenAI" },
  { id: "openrouter", env: "OPENROUTER_API_KEY", label: "OpenRouter" },
  { id: "gemini", env: "GEMINI_API_KEY", label: "Gemini" },
];

export const VOICE_SHORTLIST = [
  { id: "en-US-AriaNeural", name: "Aria", desc: "English (US) · female" },
  { id: "en-US-GuyNeural", name: "Guy", desc: "English (US) · male" },
  { id: "en-US-JennyNeural", name: "Jenny", desc: "English (US) · female" },
  { id: "en-GB-SoniaNeural", name: "Sonia", desc: "English (UK) · female" },
  { id: "en-GB-RyanNeural", name: "Ryan", desc: "English (UK) · male" },
  { id: "en-AU-NatashaNeural", name: "Natasha", desc: "English (AU) · female" },
  { id: "en-AU-WilliamNeural", name: "William", desc: "English (AU) · male" },
  { id: "es-ES-ElviraNeural", name: "Elvira", desc: "Spanish (ES) · female" },
  { id: "es-ES-AlvaroNeural", name: "Alvaro", desc: "Spanish (ES) · male" },
  { id: "es-MX-DaliaNeural", name: "Dalia", desc: "Spanish (MX) · female" },
  { id: "fr-FR-DeniseNeural", name: "Denise", desc: "French · female" },
  { id: "fr-FR-HenriNeural", name: "Henri", desc: "French · male" },
  { id: "de-DE-KatjaNeural", name: "Katja", desc: "German · female" },
  { id: "it-IT-ElsaNeural", name: "Elsa", desc: "Italian · female" },
  { id: "pt-BR-FranciscaNeural", name: "Francisca", desc: "Portuguese (BR) · female" },
];

export const ALLOW_METHODS = [
  {
    id: "link.ping",
    desc: "Liveness probe. Zero LLM cost, no state change. Lets the peer see you're online.",
  },
  {
    id: "link.ask",
    desc: "Full agent turn — peer can wake your agent and spend from your daily LLM budget. Grant only to peers you trust with cost.",
  },
  {
    id: "link.cancel",
    desc: "Abort an in-flight turn the peer started via link.ask. Useless without link.ask granted.",
  },
];

// Short network-type prefix for an address, for chips like `tailscale:7423`.
// Falls back to `tcp` for hostnames / public / auto (no recognised private IP).
export function scopeLabel(host) {
  const ip = (host || "").trim().replace(/:\d+$/, "");
  const m = ip.match(/^(\d+)\.(\d+)\.\d+\.\d+$/);
  if (m) {
    const a = Number(m[1]);
    const b = Number(m[2]);
    if (a === 100 && b >= 64 && b <= 127) return "tailscale";
    if (a === 10 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168)) return "lan";
  }
  return "tcp";
}

export function formatTcpLabel(host, port) {
  const h = (host || "").trim();
  if (!h || h === "127.0.0.1") return `tcp:${port}`;
  const truncated = h.length > 20 ? `${h.slice(0, 17)}…` : h;
  return `tcp:${truncated}:${port}`;
}

export function formatTokenCount(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M tokens`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(n < 10_000 ? 1 : 0)}K tokens`;
  return `${n} tokens`;
}

export function formatBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 ** 3).toFixed(2)} GB`;
}

export function formatLastSeen(ts) {
  if (!ts) return "never";
  const d = new Date(ts * 1000);
  const now = Date.now();
  const diff = now - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return d.toISOString().slice(0, 10);
}

export function formatLastRun(iso, status) {
  if (!status || !iso) return "never run";
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) return "never run";
  const rel = formatLastSeen(ms / 1000);
  return status === "error" ? `last run failed · ${rel}` : `ran ${rel}`;
}

export function isValidEd25519Pubkey(s) {
  if (!s) return false;
  if (!/^[A-Za-z0-9+/]+={0,2}$/.test(s)) return false;
  try {
    const raw = atob(s);
    return raw.length === 32;
  } catch {
    return false;
  }
}

export function scheduleSummary(j) {
  if (j.kind === "cron") return j.expression || "?";
  if (j.kind === "once") return `once ${j.run_at || "?"}`;
  if (j.kind === "inactivity") return `after ${j.after_hours ?? "?"}h`;
  return j.kind || "?";
}
