import {
  TASK_OPEN_LINE_RE,
  classifyMessage,
  closeStatus,
  parseDone,
  parseSkip,
  parseTaskOpen,
  parseWorking,
  validateTaskShape,
} from "../../../common/workgroupMarkers.mjs";

export {
  classifyMessage,
  closeStatus,
  parseDone,
  parseSkip,
  parseTaskOpen,
  parseWorking,
  validateTaskShape,
};

const TASK_RE = /^(?:@\S+\s+)*#task\s+#([A-Za-z0-9][A-Za-z0-9_-]{0,63})(?:\s+(.+?))?\s*$/m;
const DONE_RE = /^(?:@\S+\s+)*#done\s*(.*)$/m;

const DONE_CLOSE_RE = /^(?:@\S+\s+)*#done\s+(.+?)\s*$/i;
const ROUND_SIGNAL_RE = /^(?:@\S+\s+)*#(?:working|skip)(?:\s+.+?)?\s*$/i;

// `fold_task_state` returns `closed[-20:]`, so a full window means there is older history.
export const FOLD_CLOSED_CAP = 20;

function readMarker(body) {
  const lines = String(body || "").split("\n");
  // Both #task and #done in one post → prose, no lifecycle event (mirrors alpi parse_post ambiguity rule).
  if (lines.some((l) => TASK_OPEN_LINE_RE.test(l)) && lines.some((l) => DONE_CLOSE_RE.test(l))) {
    return null;
  }
  for (const line of lines) {
    const open = TASK_OPEN_LINE_RE.exec(line);
    if (open) {
      return { kind: "task", slug: open[1].toLowerCase(), text: (open[2] ?? "").trim() };
    }
    if (ROUND_SIGNAL_RE.test(line)) return { kind: "round" };
    const close = DONE_CLOSE_RE.exec(line);
    if (close) return { kind: "done", text: close[1].trim() };
  }
  return null;
}

// Reads the outcome off the `#done` line alone — prose above a close must never decide its colour.
export function doneOutcome(body) {
  for (const line of String(body || "").split("\n")) {
    const m = DONE_CLOSE_RE.exec(line);
    if (m) return closeStatus(m[1]);
  }
  return "done";
}

// Rows straight from `host.workgroup.tasks`: the daemon's `blocked` flag outranks the close text.
export function tasksFromFold(state) {
  if (!state || typeof state !== "object") return null;
  const rows = (Array.isArray(state.closed) ? state.closed : [])
    .slice()
    .sort((a, b) => (a.closed_seq ?? 0) - (b.closed_seq ?? 0))
    .map((row) => ({
      seq: row.closed_seq ?? null,
      slug: row.slug ?? "",
      title: "",
      status: row.blocked ? "blocked" : closeStatus(row.result),
      result: row.result ?? "",
    }));
  if (state.active) {
    rows.push({
      seq: state.active.opened_seq ?? null,
      slug: state.active.slug ?? "",
      title: state.active.title ?? "",
      status: "working",
    });
  }
  return rows;
}

// Only the hub opens (`#task`) and closes (`#done`) tasks. A member's `#skip`/`#working` are round signals that never touch task lifecycle. "preempted" means the hub opened a new `#task` before closing this one (alpi/alp/tasks.py fold_tasks).
export function deriveTasks(thread = [], hubPubkey = null) {
  const tasks = [];
  let active = null;
  for (const msg of thread) {
    const mk = readMarker(msg.body);
    const fromHub = !hubPubkey || msg.from_pubkey === hubPubkey;
    if (mk?.kind === "task" && fromHub) {
      if (active) active.status = "preempted";
      active = {
        seq: msg.seq,
        slug: mk.slug,
        title: mk.text,
        status: "working",
        contributions: 0,
      };
      tasks.push(active);
      continue;
    }
    if (!active) continue;
    if (mk?.kind === "done" && fromHub) {
      active.result = mk.text ?? "";
      active.status = closeStatus(active.result);
      active = null;
      continue;
    }
    active.contributions++;
  }
  return tasks;
}

export function findLatestTask(messages, hubPubkey = null) {
  if (!messages || messages.length === 0) return null;
  let latest = null;
  for (const m of messages) {
    if (hubPubkey && m.from_pubkey !== hubPubkey) continue;
    const body = m.body || "";
    const taskMatch = TASK_RE.exec(body);
    const doneMatch = DONE_RE.exec(body);
    if (taskMatch && doneMatch) continue; // both markers in one post → prose (mirrors alpi parse_post ambiguity rule)
    if (doneMatch && latest) {
      latest = { ...latest, state: "done", result: doneMatch[1].trim() };
      continue;
    }
    if (taskMatch) {
      const slug = taskMatch[1].toLowerCase();
      const title = (taskMatch[2] ?? "").trim();
      latest = {
        state: "open",
        slug,
        text: title || slug,
        seq: m.seq,
        result: null,
      };
    }
  }
  return latest;
}
