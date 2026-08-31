function ago(deltaMs) {
  const mins = Math.max(0, Math.round(deltaMs / 60000));
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins} min ago`;
  return `${Math.round(mins / 60)} h ago`;
}

export function describeHealth(health, nowMs = Date.now()) {
  const permission = health?.permission ?? 'undetermined';
  if (permission === 'denied') {
    return { ok: false, detail: 'Permission denied — enable alpi in system notification settings.' };
  }
  if (permission !== 'granted') {
    return { ok: false, detail: 'Permission not granted — background alerts are off.' };
  }
  if (health?.registration === 'restricted') {
    return { ok: false, detail: 'Background refresh is restricted by the OS — only live updates will arrive.' };
  }
  if (health?.registration === 'unregistered') {
    return { ok: false, detail: 'Background task not registered — reopen alpi to re-register.' };
  }

  const daemons = Array.isArray(health?.daemons) ? health.daemons : [];
  if (daemons.length === 0) {
    return { ok: false, detail: 'No paired daemon to check.' };
  }

  const healthy = daemons.filter((d) => Number(d?.lastSuccessMs) > 0 && !d?.lastError);
  const label = (d, i) => d?.name || `daemon ${i + 1}`;

  const degradedIndex = daemons.findIndex((d) => d?.degraded);
  if (healthy.length === daemons.length && degradedIndex >= 0) {
    const d = daemons[degradedIndex];
    return {
      ok: false,
      detail: `${label(d, degradedIndex)}: reachable only as a member — admin-only alerts cannot arrive.`,
    };
  }

  // Report the worst daemon, never the newest: one healthy daemon must not paint over two silent ones.
  if (healthy.length < daemons.length) {
    const index = daemons.findIndex((d) => !(Number(d?.lastSuccessMs) > 0 && !d?.lastError));
    const worst = daemons[index];
    const why = worst?.lastError
      ? `last error: ${worst.lastError}`
      : 'no successful check yet';
    const scope = daemons.length > 1 ? `${healthy.length} of ${daemons.length} daemons checking in · ` : '';
    return { ok: false, detail: `${scope}${label(worst, index)}: ${why}.` };
  }

  const oldest = daemons.reduce((a, b) => (a.lastSuccessMs <= b.lastSuccessMs ? a : b));
  if (daemons.length === 1) {
    return { ok: true, detail: `Last successful check ${ago(nowMs - oldest.lastSuccessMs)}.` };
  }
  return {
    ok: true,
    detail: `All ${daemons.length} daemons checking in · oldest check ${ago(nowMs - oldest.lastSuccessMs)}.`,
  };
}

// Dynamic so describeHealth stays importable without pulling expo-background-task into a pure context.
export async function readHealth() {
  const [{ loadConnections }, { getRegistrationStatus, groupConnectionsByDaemon }, { getPermissionStatus }, { alnStateKey, loadState }] =
    await Promise.all([
      import('../../lib/store'),
      import('./backgroundTask'),
      import('./notify'),
      import('./state'),
    ]);
  const [permission, registration, stored] = await Promise.all([
    getPermissionStatus(),
    getRegistrationStatus(),
    loadConnections(),
  ]);
  const groups = groupConnectionsByDaemon(stored?.connections);
  const daemons = [];
  for (const routes of groups) {
    const state = await loadState(alnStateKey(routes[0]));
    daemons.push({
      name: routes[0]?.name || '',
      lastSuccessMs: state.lastSuccessMs,
      lastError: state.lastError,
      degraded: state.degraded,
    });
  }
  return { permission, registration, daemons };
}
