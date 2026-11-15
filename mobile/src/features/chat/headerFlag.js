export const HIGH_USE = 0.8;

export function profileHeaderFlag({ ctxPct = 0, budgetPct = 0, paused = false }) {
  if (paused) return null;
  if (budgetPct >= HIGH_USE) return { label: `Daily budget ${Math.round(Math.min(1, budgetPct) * 100)}% used`, tone: budgetPct >= 1 ? 'danger' : 'warning' };
  if (ctxPct >= HIGH_USE) return { label: `Context ${Math.round(Math.min(1, ctxPct) * 100)}% full`, tone: 'warning' };
  return null;
}

export function workgroupHeaderFlag({ mark, status, paused = false }) {
  if (paused || !mark) return null;
  if (mark.state === 'needs') return { label: status || 'Needs you', tone: 'warning' };
  if (mark.state === 'failed') return { label: status || 'Failed', tone: 'danger' };
  return null;
}
