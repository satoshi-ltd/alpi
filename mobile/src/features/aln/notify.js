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

export async function fireForEvent(event, connection) {
  const { title, body } = formatNotification(event, connection);
  const link = deepLinkFor(event, connection);
  try {
    await Notifications.scheduleNotificationAsync({
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
