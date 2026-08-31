import * as Notifications from 'expo-notifications';

import { deepLinkFor, formatNotification } from './kinds';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

export async function getPermissionStatus() {
  try {
    const s = await Notifications.getPermissionsAsync();
    return s?.status ?? 'undetermined';
  } catch {
    return 'undetermined';
  }
}

export async function requestPermission() {
  try {
    const s = await Notifications.requestPermissionsAsync();
    return s?.status ?? 'undetermined';
  } catch {
    return 'undetermined';
  }
}

// Same daemon + same seq must reuse one OS notification id, so a live/poll double-fire replaces instead of stacking.
export function notificationIdFor(event, connection) {
  const daemon = connection?.deviceId || connection?.id || 'unknown';
  const kind = event?.event || 'event';
  const seq = Number.isFinite(event?.seq) ? event.seq : 'na';
  return `aln:${daemon}:${kind}:${seq}`.replace(/[^\w:.-]/g, '_');
}

let _forcedCount = 0;

export async function fireForEvent(event, connection, { force = false } = {}) {
  const { title, body } = formatNotification(event, connection);
  const link = deepLinkFor(event, connection);
  // A counter, not a clock: two forced fires inside one millisecond would otherwise share an id and replace each other.
  const identifier = force
    ? `${notificationIdFor(event, connection)}:${(_forcedCount += 1)}`
    : notificationIdFor(event, connection);
  try {
    await Notifications.scheduleNotificationAsync({
      identifier,
      content: {
        title,
        body,
        data: {
          link,
          connectionId: connection?.id || '',
          eventId: `${event?.event || ''}:${event?.seq ?? ''}`,
          kind: event?.event || '',
          rawData: event?.data || {},
        },
      },
      trigger: null,
    });
    return true;
  } catch {
    return false;
  }
}
