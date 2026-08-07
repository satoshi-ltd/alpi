import * as BackgroundTask from 'expo-background-task';
import * as TaskManager from 'expo-task-manager';

import { loadConnections } from '../../lib/store';
import { endpointUrl } from '../../lib/endpoint.js';
import { fireForEvent, getPermissionStatus } from './notify';
import { commitDelivered, pollConnection, WAKE_BUDGET_MS } from './poll';
import { alnStateKey } from './state';

export const TASK_NAME = 'alpi-aln-poll';

export function groupConnectionsByDaemon(connections) {
  if (!Array.isArray(connections)) return [];
  const groups = new Map();
  for (const c of connections) {
    if (!c?.id || !endpointUrl(c) || !c?.deviceId) continue;
    // A member route to a daemon returns empty history (the inbox is admin-only); left in, and sorted first by recency, it would shadow that daemon's admin route.
    if (c.role === 'member') continue;
    const list = groups.get(c.deviceId) ?? [];
    list.push(c);
    groups.set(c.deviceId, list);
  }
  const rank = (c) => (c.role === 'admin' ? 0 : 1);
  return Array.from(groups.values()).map((routes) =>
    routes.slice().sort(
      (a, b) => rank(a) - rank(b) || (Number(b.added_at) || 0) - (Number(a.added_at) || 0),
    ),
  );
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

export async function runPollOnce() {
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
    let total = 0;
    for (const routes of groups) {
      if (Date.now() - startMs > WAKE_BUDGET_MS) break;
      let pollResult = null;
      let winningRoute = null;
      let fallback = null;
      let fallbackRoute = null;
      for (const route of routes) {
        if (Date.now() - startMs > WAKE_BUDGET_MS) break;
        const result = await pollConnection(route);
        if (!result.ok) continue;
        if (result.events.length > 0) {
          pollResult = result;
          winningRoute = route;
          break;
        }
        // ok+empty (a member credential's filtered inbox, or a genuinely empty one) is only a fallback — keep searching for a route WITH events so it can't shadow an admin of the same daemon.
        if (!fallback) {
          fallback = result;
          fallbackRoute = route;
        }
      }
      if (!pollResult && fallback) {
        pollResult = fallback;
        winningRoute = fallbackRoute;
      }
      if (!pollResult || !winningRoute) continue;
      if (pollResult.events.length === 0) continue;
      await commitDelivered(alnStateKey(winningRoute), pollResult.events);
      for (const ev of pollResult.events) {
        const fired = await fireForEvent(ev, winningRoute);
        if (fired) total += 1;
      }
    }
    return { groups: groups.length, notifications: total };
  } finally {
    _runInFlight = false;
  }
}
