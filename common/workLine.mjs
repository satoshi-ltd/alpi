const VERBS = {
  read_file: "Reading", workgroup_file: "Reading", web_extract: "Reading", read_image: "Looking at",
  write_file: "Writing", edit_file: "Editing", edit: "Editing", delete_file: "Deleting", list_dir: "Listing", attach_file: "Attaching",
  terminal: "Running", shell: "Running", run: "Running", bash: "Running",
  web_fetch: "Fetching", web_search: "Searching", browser: "Browsing", research: "Researching",
  grep: "Searching", glob: "Searching", search: "Searching", find: "Searching", session_search: "Searching", workgroup_search: "Searching", recall_sessions: "Recalling",
  peer: "Asking", alp: "Asking", send_message: "Messaging", notify: "Notifying", email: "Emailing", delegate: "Delegating", workgroup_post: "Posting",
  memory: "Remembering",
};

export function stepVerb(name) {
  return VERBS[name] ?? null;
}

export function stepPhrase(name, target = "") {
  const verb = stepVerb(name);
  const what = String(target || "").trim();
  if (!verb) return what ? `Using ${name} · ${what}` : `Using ${name}`;
  return what ? `${verb} ${what}` : verb;
}

function span(tools) {
  const timed = tools.filter((t) => Number.isFinite(t.start));
  if (!timed.length) return null;
  const first = Math.min(...timed.map((t) => t.start));
  const last = Math.max(...timed.map((t) => t.start + (Number(t.seconds) || 0)));
  return Math.max(0, last - first);
}

function proseLines(note) {
  const out = [];
  let fenced = false;
  for (const raw of String(note ?? "").split("\n")) {
    const line = raw.trim();
    if (/^(```|~~~)/.test(line)) {
      fenced = !fenced;
      out.push("");
      continue;
    }
    out.push(fenced || /^([-*_]\s*){3,}$/.test(line) || /^\|.*\|$/.test(line) ? "" : line);
  }
  return out;
}

export function notePhrase(note) {
  const paragraphs = proseLines(note).join("\n").split(/\n\s*\n/).map((s) => s.trim()).filter(Boolean);
  const line = (paragraphs[paragraphs.length - 1] ?? "").split("\n")[0];
  return line
    .replace(/^#{1,6}\s+|^[-*+]\s+(\[[ xX]\]\s+)?|^\d+\.\s+|^>\s*/, "")
    .replace(/(\*\*|\*|~~|`)(?=\S)(.+?)(?<=\S)\1/g, "$2")
    .trim();
}

export function workSummary(items, { thinking = false, running: turnRunning = false, writing = false, note = "" } = {}) {
  const list = Array.isArray(items) ? items : [];
  const tools = list.filter((i) => i.kind === "tool");
  const thoughts = list.filter((i) => i.kind === "thought" && (i.live || String(i.text || "").trim() || i.seconds >= 1));
  const runningTool = tools.find((t) => t.ok == null);
  const running = turnRunning || thinking || !!runningTool || thoughts.some((t) => t.live);
  const last = list[list.length - 1];
  const liveThought = last?.kind === "thought" && last.live;
  const said = notePhrase(note);
  const phrase = !running ? "" : runningTool && !liveThought ? stepPhrase(runningTool.name, runningTool.target) : said ? said : writing && !liveThought ? "Writing" : "Thinking";
  const toolSpan = span(tools);
  const toolAt = list.flatMap((i, n) => (i.kind === "tool" ? [n] : []));
  const outside = thoughts.filter((t) => { const n = list.indexOf(t); return n < toolAt[0] || n > toolAt[toolAt.length - 1]; })
    .reduce((n, t) => n + (Number(t.seconds) || 0), 0);
  const seconds = toolSpan != null
    ? toolSpan + outside
    : tools.reduce((n, t) => n + (Number(t.seconds) || 0), 0) + thoughts.reduce((n, t) => n + (Number(t.seconds) || 0), 0);
  return {
    running,
    phrase,
    steps: tools.length + thoughts.filter((t) => !t.live).length,
    failed: tools.filter((t) => t.ok === false).length,
    seconds,
  };
}

export function workClock(seconds) {
  const s = Number(seconds);
  if (!Number.isFinite(s) || s <= 0) return "";
  if (s < 1) return `${s.toFixed(1)}s`;
  if (s < 60) return `${Math.round(s)}s`;
  const m = Math.floor(s / 60);
  const rest = Math.round(s - m * 60);
  return rest ? `${m}m ${rest}s` : `${m}m`;
}
