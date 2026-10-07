const KEY = { memory: "memory", skills: "skills", schedule: "schedules" };
const NOUN = {
  memory: ["file needs you", "files need you"],
  skills: ["skill needs you", "skills need you"],
  schedule: ["job needs you", "jobs need you"],
};

export function attentionItems(att, panelId) {
  const key = KEY[panelId];
  const list = key && att ? att[key] : null;
  return Array.isArray(list) ? list : [];
}

export function flagCount(att, panelId) {
  return attentionItems(att, panelId).length;
}

export function totalFlags(att) {
  return Object.keys(KEY).reduce((sum, id) => sum + flagCount(att, id), 0);
}

export function memoryItem(att, file) {
  return attentionItems(att, "memory").find((i) => i.file === file) ?? null;
}

export function skillItem(att, category, name) {
  return attentionItems(att, "skills").find((i) => i.name === name && (i.category ?? null) === (category ?? null)) ?? null;
}

export function jobItem(att, id) {
  return attentionItems(att, "schedule").find((i) => i.id === id) ?? null;
}

export function memoryWord(item) {
  return item.over ? "over" : "full";
}

export function skillWord(item) {
  return item.problem === "lint" ? "lint" : "missing";
}

export function memoryBanner(item) {
  const used = `${item.used.toLocaleString("en-US")} / ${item.limit.toLocaleString("en-US")}`;
  if (item.over) {
    const by = (item.used - item.limit).toLocaleString("en-US");
    return {
      lead: `Over its limit by ${by} characters`,
      detail: `${used}. Every turn pays for the part that does not fit. Shorten it or move durable facts to a skill’s state.`,
    };
  }
  return { lead: `Nearly full: ${item.pct}% of its limit`, detail: `${used}. The next additions will be refused until it is consolidated.` };
}

export function skillBanner(item) {
  if (item.problem === "lint") {
    return { lead: "Does not pass lint", detail: `${item.message}. The skill is not offered to the model until it passes.` };
  }
  return { lead: "Missing what it requires", detail: `${item.message}. The skill stays inactive until it is provided.` };
}

export function jobBanner(item, when = "") {
  const reason = item.message ? `${item.message}.` : "The run did not complete.";
  const good = item.last_ok_at ? ` Last good run: ${when || item.last_ok_at}.` : " It has not succeeded yet.";
  return { lead: "Last run failed", detail: `${reason}${good}` };
}

export function attentionHelper(att, panelId) {
  const items = attentionItems(att, panelId);
  if (items.length === 0) return null;
  if (panelId === "memory") {
    const over = items.filter((i) => i.over).length;
    if (over) return `${over} over ${over === 1 ? "its" : "their"} limit`;
    return `${items.length} nearly full`;
  }
  if (panelId === "skills") {
    const lint = items.filter((i) => i.problem === "lint").length;
    const missing = items.length - lint;
    return [lint ? `${lint} fails lint` : null, missing ? `${missing} missing what it requires` : null].filter(Boolean).join(" · ");
  }
  return `${items.length} failed`;
}

export function attentionLabel(att, panelId) {
  const n = flagCount(att, panelId);
  if (n === 0) return "";
  const [one, many] = NOUN[panelId] ?? ["item needs you", "items need you"];
  return `${n} ${n === 1 ? one : many}`;
}

const UNITS = [[86400, "d"], [3600, "h"], [60, "m"]];

export function nextRunWord(job, now = Date.now()) {
  if (job.paused) return "paused";
  if (job.last_run_status === "error") return "failed";
  const at = Date.parse(job.next_fire || "");
  if (!Number.isFinite(at)) return "";
  const secs = Math.max(0, Math.round((at - now) / 1000));
  for (const [size, unit] of UNITS) {
    if (secs >= size) return `in ${Math.floor(secs / size)}${unit}`;
  }
  return "now";
}

export function jobGroups(jobs, now = Date.now()) {
  const needs = [];
  const active = [];
  const paused = [];
  for (const job of jobs ?? []) {
    if (job.paused) paused.push(job);
    else if (job.last_run_status === "error") needs.push(job);
    else active.push(job);
  }
  return [
    { id: "needs", label: "Needs you", jobs: needs },
    { id: "active", label: "Active", jobs: active },
    { id: "paused", label: "Paused", jobs: paused },
  ].filter((g) => g.jobs.length > 0);
}
