import { Banner } from './Banner';

export const DAEMON_STATUS_BANNERS = {
  offline: {
    kind: 'danger',
    message: 'Daemon unreachable. Reconnecting…',
    action: 'Retry',
  },
  disabled: {
    kind: 'warning',
    message: 'Connection disabled by host. Ask an admin to enable it in Settings → Connections.',
    action: null,
  },
  'auth-failed': {
    kind: 'danger',
    message: 'Token rejected by daemon. Re-pair this phone to continue.',
    action: null,
  },
};

const DOWN = new Set(Object.keys(DAEMON_STATUS_BANNERS));

export function isDaemonDown(status) {
  return DOWN.has(status);
}

export function DaemonBanner({ status, paired = true, onRetry }) {
  const entry = paired && DOWN.has(status) ? DAEMON_STATUS_BANNERS[status] : null;
  if (!entry) return null;
  return (
    <Banner kind={entry.kind} action={entry.action && onRetry ? entry.action : null} onAction={onRetry}>
      {entry.message}
    </Banner>
  );
}
