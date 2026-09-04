const STORAGE_KEY = "alpi.connections.lastActive.v1";
const UNREACHABLE = new Set(["offline", "disabled", "auth-failed"]);

export function readLastActive() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

export function stampLastActive(id, nowSeconds = Math.floor(Date.now() / 1000)) {
  if (!id) return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...readLastActive(), [id]: nowSeconds }));
  } catch {
    // Storage may be unavailable; ordering then falls back to reachability and name.
  }
}

export function orderConnections(connections = [], lastActive = readLastActive()) {
  const rank = (c) => (c.kind === "local" ? 0 : UNREACHABLE.has(c.status) ? 2 : 1);
  return [...connections].sort((left, right) =>
    rank(left) - rank(right)
      || Number(lastActive[right.id] || 0) - Number(lastActive[left.id] || 0)
      || String(left.name || "").localeCompare(String(right.name || "")),
  );
}
