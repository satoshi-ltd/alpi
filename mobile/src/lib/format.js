export function formatClock(epoch) {
  if (!epoch) return '';
  const ms = typeof epoch === 'string' ? Date.parse(epoch) : epoch * 1000;
  if (!Number.isFinite(ms)) return '';
  const d = new Date(ms);
  return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

export function formatRelative(epoch) {
  if (!epoch) return '';
  const now = Date.now() / 1000;
  const diff = now - epoch;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d ago`;
  const d = new Date(epoch * 1000);
  return d.toLocaleDateString();
}
