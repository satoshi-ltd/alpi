import { workgroupMark, workgroupStatusLine } from "./workgroupMarkState.mjs";

export const WORKGROUP_FILTERS = [
  { id: "all", label: "All" },
  { id: "active", label: "Active" },
  { id: "queued", label: "Queued" },
  { id: "paused", label: "Paused" },
];

export const WORKGROUP_GROUPS = [
  { id: "needs", label: "Needs you", states: ["needs", "error"] },
  { id: "active", label: "Working", states: ["active"] },
  { id: "queued", label: "Queued", states: ["queued"] },
  { id: "idle", label: "Idle", states: ["idle"] },
  { id: "paused", label: "Paused", states: ["paused"] },
];

const URGENT = new Set(["active", "needs", "error"]);
const FILTER_NOUN = { all: "workgroup", active: "active workgroup", queued: "queued workgroup", paused: "paused workgroup" };

export function workgroupState(workgroup, task, busy, mark) {
  if (workgroup.paused) return { id: "paused", label: "Paused" };
  if (workgroup.pipeline_status === "queued") {
    const position = Number(workgroup.queue_position || 0);
    return { id: "queued", label: position ? `Queued · #${position}` : "Queued" };
  }
  if (workgroup.pipeline_status === "blocked") {
    return { id: "needs", label: workgroupStatusLine(mark) ?? "Needs you" };
  }
  if (["running", "between"].includes(workgroup.pipeline_status)) {
    if (mark.step) return { id: "active", label: workgroupStatusLine(mark) };
    return { id: "active", label: task?.state === "open" && task.slug ? `Working · ${task.slug}` : "Working" };
  }
  if (workgroup.pipeline_status === "completed") return { id: "idle", label: "Idle" };
  if (task?.state === "error") return { id: "error", label: "Needs attention" };
  if (mark.state === "running") return { id: "active", label: workgroupStatusLine(mark) ?? "Working" };
  return { id: "idle", label: "Idle" };
}

export function workgroupRowState({ workgroup, run = null, task = null, busy = false }) {
  const mark = workgroupMark({ workgroup, run, task, busy });
  return { mark, state: workgroupState(workgroup, task, busy, mark) };
}

export function stateRank(stateId) {
  return URGENT.has(stateId) ? 0 : stateId === "queued" ? 1 : 2;
}

export function inFilter(stateId, filter) {
  if (filter === "active") return URGENT.has(stateId);
  if (filter === "queued" || filter === "paused") return stateId === filter;
  return true;
}

export function filterCounts(stateIds) {
  const ids = [...stateIds];
  return Object.fromEntries(WORKGROUP_FILTERS.map(({ id }) => [id, ids.filter((stateId) => inFilter(stateId, id)).length]));
}

// The Active filter holds what is working and what waits for the owner; a line that says "working" counts only the first.
export function workgroupSummaryLine(stateIds) {
  const ids = [...stateIds];
  const working = ids.filter((stateId) => stateId === "active").length;
  const waiting = ids.filter((stateId) => stateId === "needs" || stateId === "error").length;
  const parts = [String(ids.length), `${working} working`];
  if (waiting) parts.push(`${waiting} ${waiting === 1 ? "needs" : "need"} you`);
  return parts.join(" · ");
}

export function groupWorkgroupRows(rows) {
  return WORKGROUP_GROUPS
    .map((group) => ({ id: group.id, label: group.label, rows: rows.filter((row) => group.states.includes(row.state.id)) }))
    .filter((group) => group.rows.length > 0);
}

export function workgroupStatusLabel(state) {
  return state.id === "idle" ? null : state.label;
}

export function noMatchLine(filter, query) {
  const needle = String(query ?? "").trim();
  const noun = FILTER_NOUN[filter] ?? FILTER_NOUN.all;
  return needle ? `No ${noun} matches ${needle}.` : `No ${noun}s right now.`;
}

const queuePosition = (row) => Number(row.raw?.queue_position || 0);

export function rosterWorkgroups(rows, cap) {
  const moving = rows.filter((row) => stateRank(row.stateId) < 2)
    .sort((a, b) => stateRank(a.stateId) - stateRank(b.stateId) || queuePosition(a) - queuePosition(b));
  const resting = rows.filter((row) => stateRank(row.stateId) >= 2);
  return [...moving, ...resting.slice(0, Math.max(0, cap - moving.length))];
}
