import { pairingLinkFromParams } from '../../lib/pairing';

export function relativeSeen(ts) {
  const n = Number(ts);
  if (!n) return 'never';
  const seconds = Math.max(0, Math.floor(Date.now() / 1000 - n));
  if (seconds < 60) return 'now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

export function deviceTitle(device) {
  return device?.name || `${device?.client || 'unknown'} device`;
}

export function deviceMeta(device) {
  return [
    device?.client || 'unknown',
    device?.app_version,
    relativeSeen(device?.last_seen),
    device?.provisioner ? 'provisioner' : null,
    device?.expired ? 'expired' : null,
  ]
    .filter(Boolean)
    .join(' · ');
}

export function scopeLabel(row) {
  if (row?.role === 'admin') return 'all profiles';
  const scope = row?.profile_scope ?? [];
  return scope.length ? scope.join(', ') : 'all profiles';
}

export function sessionScopeLabel(row) {
  return row?.session_scope === 'device' ? 'per device' : 'per connection';
}

export function pairingLink(payload, endpointUrl) {
  const url = endpointUrl || payload?.url || payload?.endpoints?.[0]?.url || '';
  return pairingLinkFromParams({
    url,
    name: payload?.pairing_name || payload?.label || 'Alpi',
    pairing_token: payload?.pairing_token || '',
    token: payload?.pairing_token ? '' : payload?.token || '',
    connection_id: payload?.connection_id || '',
  });
}
