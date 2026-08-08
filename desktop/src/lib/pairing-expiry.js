export function pairingSecondsRemaining(expiresAt, now = Date.now()) {
  const expiresMs = Number(expiresAt) * 1000;
  if (!Number.isFinite(expiresMs) || expiresMs <= 0) return null;
  return Math.max(0, Math.ceil((expiresMs - now) / 1000));
}

export function pairingDisplayStatus(status, expiresAt, now = Date.now()) {
  const remaining = pairingSecondsRemaining(expiresAt, now);
  return status === "pending" && remaining === 0 ? "expired" : status;
}

export function pairingExpiryText(expiresAt, status = "pending", now = Date.now()) {
  const displayStatus = pairingDisplayStatus(status, expiresAt, now);
  if (displayStatus === "expired") {
    const expiresMs = Number(expiresAt) * 1000;
    if (!Number.isFinite(expiresMs) || expiresMs <= 0) return "expired";
    const elapsed = Math.max(0, Math.floor((now - expiresMs) / 1000));
    if (elapsed < 60) return elapsed ? `expired ${elapsed}s ago` : "expired just now";
    return `expired ${Math.floor(elapsed / 60)}m ago`;
  }
  if (displayStatus !== "pending") return displayStatus;
  const remaining = pairingSecondsRemaining(expiresAt, now);
  if (remaining == null) return "pending";
  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;
  if (!minutes) return `expires in ${seconds}s`;
  return `expires in ${minutes}m ${seconds}s`;
}
