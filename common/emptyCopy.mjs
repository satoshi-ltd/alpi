export const EMPTY = {
  providers: { title: "No providers yet", hint: "Add an API key or a local Ollama to pick models." },
  models: { title: "No models yet", hint: "Add a provider first." },
  email: { title: "No email accounts yet", hint: "Connect one so the agent can read and send mail." },
  mcp: { title: "No MCP servers yet", hint: "Add one to give the agent external tools." },
  mcpTools: { title: "No tools exposed", hint: "This server lists none." },
  mcpEnv: { title: "No env keys", hint: "" },
  mcpArgs: { title: "No arguments", hint: "" },
  peers: { title: "No peers yet", hint: "Trust another alpi to talk to it." },
  peerMethods: { title: "No methods allowed", hint: "" },
  members: { title: "No members yet", hint: "Invite a profile to join." },
  devices: { title: "No devices yet", hint: "Add one to get a pairing link." },
  storage: { title: "Nothing stored yet", hint: "Disk use shows up once this profile starts working." },
  usage: { title: "No usage yet", hint: "Tokens and spend appear after the first turn." },
  workgroupUsage: { title: "No usage yet", hint: "Spend appears once the hub posts or settles a task." },
  workgroups: { title: "No workgroups yet", hint: "A workgroup is a hub profile plus the members it directs." },
  roster: { title: "No profiles or workgroups yet", hint: "Create one to begin." },
  profiles: { title: "No profiles yet", hint: "" },
  skills: { title: "No skills installed", hint: "Ask the agent to build one." },
  tools: { title: "No tools registered", hint: "The daemon exposes none to this profile." },
  schedule: { title: "No scheduled jobs", hint: "Ask the agent to set one up." },
  sessions: { title: "No sessions yet", hint: "A session starts with your first message." },
  connections: { title: "No paired apps yet", hint: "Create a connection and share its pairing link with a phone or desktop." },
  posts: { title: "No posts yet", hint: "Direct the hub to open a #task." },
  tasks: { title: "No tasks yet", hint: "Direct the hub to open one." },
  activity: { title: "Nothing running", hint: "Running turns, workgroup phases, schedules and anything waiting on you show up here." },
  notifications: { title: "No notifications yet", hint: "Notifications land here when an agent notifies you or a scheduled job fails." },
  launchPipeline: { title: "No launch pipeline", hint: "Nothing starts until a trigger." },
  noPipelines: { title: "No pipelines", hint: "This is a deliberation workgroup." },
  retiredPipelines: { title: "Retired pipeline shape", hint: "The daemon skips this workgroup, so relaunch it from its recipe." },
  toolOutput: { title: "No output", hint: "" },
  endpoint: { title: "No advertised endpoint", hint: "Set one under Network." },
  checks: { title: "No successful check yet", hint: "" },
  memory: { title: "No memory files", hint: "" },
  briefing: { title: "No briefing yet", hint: "" },
  accounts: { title: "No accounts yet", hint: "" },
  matches: { title: "No matches", hint: "Try a different query, or clear it." },
};

export function emptyLine(key) {
  return EMPTY[key].title;
}

export function postsHint(hub) {
  return `Direct @${hub} to open a #task.`;
}

export function usageRangeEmpty(days) {
  return `No usage in the last ${days} ${days === 1 ? "day" : "days"}`;
}
