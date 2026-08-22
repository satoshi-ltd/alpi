export const HEX_RE = /^#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$/;

export const FIELD_KEYS = {
  bio: "public_bio",
  workspace: "workspace",
  model: "model",
  accent: "tui.accent",
  reasoningEffort: "model_reasoning.effort",
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

export const RECLAIM_NOTES = {
  sessions: "chats older than 30 days",
  generated: "generated files older than 30 days",
  mentions: "all @-mention threads",
  workgroups: "all workgroup history",
};

export const STORAGE_GROUPS = [
  { key: "conversations", label: "Conversations", usage: ["sessions", "workgroups", "mentions"], desc: "chats, workgroup transcripts and @-mention threads" },
  { key: "skills", label: "Skills", usage: ["skills"], content: true, desc: STORAGE_SCOPE.skills },
  { key: "memories", label: "Memories", usage: ["memories"], content: true, desc: STORAGE_SCOPE.memories },
  { key: "files", label: "Files", usage: ["outputs", "generated", "attachments"], desc: "notifications inbox, generated + staged files" },
  { key: "knowledge", label: "Knowledge", usage: ["knowledge"], desc: "workspace embeddings (sqlite-vec store)" },
  { key: "caches", label: "Caches", usage: ["audio"], desc: "TTS output + inbound media — regenerated on demand" },
  { key: "logs", label: "Logs", usage: ["logs", "schedule"], desc: "agent, approval, schedule + curator diagnostics" },
];

export const PAID_PROVIDERS = [
  { id: "anthropic", env: "ANTHROPIC_API_KEY", label: "Anthropic" },
  { id: "openai", env: "OPENAI_API_KEY", label: "OpenAI" },
  { id: "openrouter", env: "OPENROUTER_API_KEY", label: "OpenRouter" },
  { id: "gemini", env: "GEMINI_API_KEY", label: "Gemini" },
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

export function providerPills(profile, ollamaErrors = []) {
  const errByName = new Map((ollamaErrors ?? []).map((e) => [e.name, e]));
  const cloud = (profile.provider_keys ?? []).map((k) => ({
    label: String(k.env || "").replace(/_API_KEY$/, "").toLowerCase(),
    error: null,
  }));
  const ollama = (profile.provider_ollama ?? []).map((o) => {
    const err = errByName.get(o.name) ?? null;
    return {
      label: `ollama/${o.name}`,
      error: err ? `${err.url} — ${err.detail}` : null,
    };
  });
  return [...cloud, ...ollama].filter((p) => p.label);
}
