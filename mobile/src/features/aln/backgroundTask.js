import * as BackgroundTask from 'expo-background-task';
import * as TaskManager from 'expo-task-manager';

import { loadConnections } from '../../lib/store';
import { fireForEvent, getPermissionStatus } from './notify';
import { commitDelivered, pollConnection, WAKE_BUDGET_MS } from './poll';

export const TASK_NAME = 'alpi-aln-poll';

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

export async function runPollOnce({ force = false } = {}) {
  const startMs = Date.now();
  const perm = await getPermissionStatus();
  if (perm !== 'granted') {
    return { connections: 0, notifications: 0, skipped: 'no-permission' };
  }
  const state = await loadConnections();
  const connections = Array.isArray(state?.connections) ? state.connections : [];
  let total = 0;
  for (const conn of connections) {
    if (!conn?.id || !conn?.ip || !conn?.port) continue;
    if (Date.now() - startMs > WAKE_BUDGET_MS) break;
    const { events } = await pollConnection(conn);
    const delivered = [];
    for (const ev of events) {
      const fired = await fireForEvent(ev, conn, { force });
      if (!fired) break;
      delivered.push(ev);
      total += 1;
    }
    if (delivered.length > 0) {
      await commitDelivered(conn.id, delivered);
    }
  }
  return { connections: connections.length, notifications: total };
}
