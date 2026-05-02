// Cache `taskByWorkgroup` and mtimes in localStorage.
// Null means "recompute later".

const KEY = "alpi:workgroup-task-cache:v2";

const empty = () => ({ tasks: {}, mtimes: {} });

export function loadTaskCache() {
  try {
    const raw = localStorage.getItem(KEY);
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

export function saveTaskCache(state) {
  try {
    const tasks = {};
    for (const [k, v] of Object.entries(state?.tasks ?? {})) {
      if (v != null) tasks[k] = v;
    }
    localStorage.setItem(
      KEY,
      JSON.stringify({ tasks, mtimes: state?.mtimes ?? {} }),
    );
  } catch {
  }
}
