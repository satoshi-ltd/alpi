const KEY_PREFIX = "alpi:workgroup-task-cache:v3";

const empty = () => ({ tasks: {}, mtimes: {} });

function key(connectionId) {
  return `${KEY_PREFIX}:${connectionId || "local"}`;
}

export function loadTaskCache(connectionId) {
  try {
    const raw = localStorage.getItem(key(connectionId));
    if (!raw) return empty();
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return empty();
    const rawTasks =
      parsed.tasks && typeof parsed.tasks === "object" ? parsed.tasks : {};
    const tasks = {};
    for (const [k, v] of Object.entries(rawTasks)) {
      if (v != null) tasks[k] = v;
    }
    return {
      tasks,
      mtimes:
        parsed.mtimes && typeof parsed.mtimes === "object" ? parsed.mtimes : {},
    };
  } catch {
    return empty();
  }
}

export function saveTaskCache(connectionId, state) {
  try {
    const tasks = {};
    for (const [k, v] of Object.entries(state?.tasks ?? {})) {
      if (v != null) tasks[k] = v;
    }
    localStorage.setItem(
      key(connectionId),
      JSON.stringify({ tasks, mtimes: state?.mtimes ?? {} }),
    );
  } catch {
    /* */
  }
}
