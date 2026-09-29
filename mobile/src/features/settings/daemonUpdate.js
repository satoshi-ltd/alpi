const MANUAL_HINT = 'Docker: docker compose pull, then docker compose up -d · source install: git pull and restart the daemon';

export function updateOutcome(result) {
  const r = result ?? {};
  if (r.updated) {
    return { title: r.latest ? `Updating to alpi ${r.latest}` : 'Update started', message: 'the daemon restarts on its own' };
  }
  switch (r.reason) {
    case 'up-to-date':
      return { title: 'Already up to date', message: r.current ? `alpi ${r.current}` : undefined };
    case 'manual':
      return { title: "Can't self-update this install", message: MANUAL_HINT };
    case 'offline':
      return { title: 'Update check failed', message: 'the daemon could not reach PyPI' };
    default:
      return { title: 'Update failed', message: r.reason ? String(r.reason) : 'unknown reason' };
  }
}
