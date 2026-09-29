export const EMPTY = {
  providers: { title: "No providers yet", hint: "add an API key or a local Ollama to pick models" },
  models: { title: "No models yet", hint: "add a provider first" },
  email: { title: "No email accounts yet", hint: "connect one so the agent can read and send mail" },
  mcp: { title: "No MCP servers yet", hint: "add one to give the agent external tools" },
  mcpTools: { title: "No tools exposed", hint: "this server lists none" },
  peers: { title: "No peers yet", hint: "trust another alpi to talk to it" },
  members: { title: "No members yet", hint: "invite a profile to join" },
  devices: { title: "No devices yet", hint: "add one to get a pairing link" },
  storage: { title: "Nothing stored yet", hint: "disk use shows up once this profile starts working" },
  usage: { title: "No usage yet", hint: "tokens and spend appear after the first turn" },
  workgroupUsage: { title: "No usage yet", hint: "spend appears once the hub posts or settles a task" },
  workgroups: { title: "No workgroups yet", hint: "create one with the + beside Workgroups in the roster" },
  skills: { title: "No skills installed", hint: "drop a SKILL.md under ~/.alpi/profiles/<name>/skills/" },
  tools: { title: "No tools registered", hint: "the daemon exposes none to this profile" },
  schedule: { title: "No scheduled jobs", hint: "ask the agent to set one up" },
  sessions: { title: "No previous sessions", hint: "start one to fill the list" },
  connections: { title: "No paired apps yet", hint: "create a connection and share its pairing link with a phone or desktop" },
};

export function emptyLine(key) {
  const entry = EMPTY[key];
  return `${entry.title} · ${entry.hint}`;
}

export function usageRangeEmpty(days) {
  return `No usage in the last ${days} ${days === 1 ? "day" : "days"}`;
}
