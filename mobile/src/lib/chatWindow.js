// turnIndex must be ABSOLUTE (turnsBase + local): rewrite_from_turn truncates the session server-side by absolute count, and a tail slice shifts local indices.
export function visibleWindow(full, pageSize, turnsBase = 0) {
  const start = Math.max(0, full.length - pageSize);
  const out = [];
  for (let i = full.length - 1; i >= start; i -= 1) {
    out.push({ turn: full[i], turnIndex: turnsBase + i });
  }
  return out;
}
