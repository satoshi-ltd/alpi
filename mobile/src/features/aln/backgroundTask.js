import * as BackgroundTask from 'expo-background-task';
import * as TaskManager from 'expo-task-manager';

import { loadConnections } from '../../lib/store';
import { endpointUrl } from '../../lib/endpoint.js';
import { deliverEvents } from './deliver';
import { getPermissionStatus } from './notify';
import { pollConnection, POLL_TIMEOUT_MS, recordGroupHealth, WAKE_BUDGET_MS } from './poll';
import { loadFlag, saveFlag } from './state';

export const TASK_NAME = 'alpi-aln-poll';

const MAX_CONCURRENT_GROUPS = 3;

export function groupConnectionsByDaemon(connections) {
  if (!Array.isArray(connections)) return [];
  const groups = new Map();
  for (const c of connections) {
    if (!c?.id || !endpointUrl(c) || !c?.deviceId) continue;
    const list = groups.get(c.deviceId) ?? [];
    list.push(c);
    groups.set(c.deviceId, list);
  }
  // A member route sees a filtered inbox, so it must sort behind admin — the ok-and-empty fallback below then keeps it from shadowing one.
  const rank = (c) => (c.role === 'admin' ? 0 : 1);
  return Array.from(groups.values()).map((routes) =>
    routes.slice().sort(
      (a, b) => rank(a) - rank(b) || (Number(b.added_at) || 0) - (Number(a.added_at) || 0),
    ),
  );
}

async function nextWakeIndex(count) {
  if (count <= 1) return 0;
  const raw = Number(await loadFlag('wakeIndex', 0));
  const start = Number.isFinite(raw) ? ((raw % count) + count) % count : 0;
  await saveFlag('wakeIndex', (start + 1) % count);
  return start;
}

async function pollGroup(routes, remainingMs, deadline) {
  let winner = null;
  let winningRoute = null;
  let fallback = null;
  let fallbackRoute = null;
  let reached = false;
  let adminReached = false;
  let error = '';
  const hasAdmin = routes.some((r) => r.role === 'admin');
  for (const route of routes) {
    if (remainingMs() <= POLL_TIMEOUT_MS) break;
    const result = await pollConnection(route);
    if (!result.ok) {
      if (!error) error = result.error;
      continue;
    }
    reached = true;
    if (route.role === 'admin') adminReached = true;
    if (result.events.length > 0) {
      winner = result;
      winningRoute = route;
      break;
    }
    if (!fallback) {
      fallback = result;
      fallbackRoute = route;
    }
  }
  // Degraded, not healthy: a member fallback answering while the admin route is down cannot carry admin-only alerts.
  await recordGroupHealth(routes[0], { ok: reached, error, degraded: reached && hasAdmin && !adminReached });

  if (!winner && fallback) {
    winner = fallback;
    winningRoute = fallbackRoute;
  }
  if (!winner || !winningRoute) return 0;

  // A member sees a role-filtered stream, so its page's max seq is not a cursor an admin route can trust.
  const advanceCursor = !hasAdmin || winningRoute.role === 'admin';
  return deliverEvents(winner.events, winningRoute, { advanceCursor, deadline, nextSeq: winner.nextSeq ?? null });
}

let _runInFlight = false;

if (!TaskManager.isTaskDefined(TASK_NAME)) {
  TaskManager.defineTask(TASK_NAME, async () => {
    try {
      await runPollOnce();
      return BackgroundTask.BackgroundTaskResult.Success;
    } catch {
      return BackgroundTask.BackgroundTaskResult.Failed;
    }
  });
}

export async function ensureRegistered() {
  try {
    const status = await BackgroundTask.getStatusAsync();
    if (status === BackgroundTask.BackgroundTaskStatus.Restricted) return false;
    await BackgroundTask.registerTaskAsync(TASK_NAME, {
      minimumInterval: 15,
    });
    return true;
  } catch {
    return false;
  }
}

export async function unregister() {
  try {
    await BackgroundTask.unregisterTaskAsync(TASK_NAME);
  } catch { /* */ }
}

export async function getRegistrationStatus() {
  try {
    const status = await BackgroundTask.getStatusAsync();
    if (status === BackgroundTask.BackgroundTaskStatus.Restricted) {
      return 'restricted';
    }
    const registered = await TaskManager.isTaskRegisteredAsync(TASK_NAME);
    return registered ? 'registered' : 'unregistered';
  } catch {
    return 'unknown';
  }
}

export async function runPollOnce({ budgetMs = WAKE_BUDGET_MS } = {}) {
  if (_runInFlight) {
    return { groups: 0, notifications: 0, skipped: 'in-flight' };
  }
  _runInFlight = true;
  try {
    const startMs = Date.now();
    const perm = await getPermissionStatus();
    if (perm !== 'granted') {
      return { groups: 0, notifications: 0, skipped: 'no-permission' };
    }
    const state = await loadConnections();
    const groups = groupConnectionsByDaemon(state?.connections);
    if (groups.length === 0) return { groups: 0, notifications: 0 };

    // Group order is stable, so without a persisted offset the tail of the list starves on every wake.
    const offset = await nextWakeIndex(groups.length);
    const ordered = groups.map((_, i) => groups[(offset + i) % groups.length]);
    const remainingMs = () => budgetMs - (Date.now() - startMs);
    const deadline = startMs + budgetMs;

    let total = 0;
    let cursor = 0;
    const lane = async () => {
      for (;;) {
        if (remainingMs() <= POLL_TIMEOUT_MS) return;
        const index = cursor;
        if (index >= ordered.length) return;
        cursor += 1;
        // Per group: one unreachable daemon must not abort the whole wake.
        let fired = 0;
        try {
          fired = await pollGroup(ordered[index], remainingMs, deadline);
        } catch { /* */ }
        total += fired;
      }
    };
    const lanes = Math.min(MAX_CONCURRENT_GROUPS, ordered.length);
    await Promise.all(Array.from({ length: lanes }, lane));

    return { groups: groups.length, notifications: total };
  } finally {
    _runInFlight = false;
  }
}
