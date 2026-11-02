export const DEFAULT_WAIT_SECONDS = 600;
export const WAIT_CHOICES = [120, 300, 600, 1200, 1800, 3600];
export const CAP_CHOICES = [null, 1, 5, 10, 25, 50, 100];

export function waitLabel(seconds) {
  const s = Math.round(Number(seconds) || DEFAULT_WAIT_SECONDS);
  return s % 60 ? `${s} s` : `${s / 60} min`;
}

export function capLabel(usd) {
  return usd == null ? "No cap" : `$${Number(usd).toFixed(2)}`;
}

export function runLimitParams({ waitSeconds, budgetUsd } = {}) {
  const out = {};
  if (waitSeconds != null) out.quorum_timeout_seconds = Math.round(waitSeconds);
  if (budgetUsd != null) out.budget_usd = budgetUsd;
  return out;
}

// A row without the key comes from a daemon that does not report the wait; a null value means the 10-minute default.
export function workgroupWaitLabel(row) {
  if (!row || !Object.prototype.hasOwnProperty.call(row, "quorum_timeout_seconds")) return null;
  return waitLabel(row.quorum_timeout_seconds || DEFAULT_WAIT_SECONDS);
}
