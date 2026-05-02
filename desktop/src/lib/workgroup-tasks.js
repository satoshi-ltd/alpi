const TASK_RE = /^(?:@\S+\s+)*#task\s+(.+?)\s*$/m;
const DONE_RE = /^(?:@\S+\s+)*#done\s*(.*)$/m;

export function findLatestTask(messages, hubPubkey = null) {
  if (!messages || messages.length === 0) return null;
  let latest = null;
  for (const m of messages) {
    if (hubPubkey && m.from_pubkey !== hubPubkey) continue;
    const doneMatch = DONE_RE.exec(m.body || "");
    if (doneMatch && latest) {
      latest = { ...latest, state: "done", result: doneMatch[1].trim() };
      continue;
    }
    const taskMatch = TASK_RE.exec(m.body || "");
    if (taskMatch) {
      latest = { state: "open", text: taskMatch[1], seq: m.seq, result: null };
    }
  }
  return latest;
}
