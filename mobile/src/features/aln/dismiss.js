let loading = null;

function load() {
  loading ??= import('expo-notifications').catch(() => null);
  return loading;
}

export async function dismissRequestNotifications(requestId) {
  if (!requestId) return 0;
  const n = await load();
  try {
    const presented = (await n?.getPresentedNotificationsAsync?.()) ?? [];
    const matches = presented.filter((item) => {
      const data = item?.request?.content?.data ?? {};
      return data.requestId === requestId || data.rawData?.request_id === requestId;
    });
    await Promise.all(matches.map((item) => n.dismissNotificationAsync(item.request.identifier)));
    return matches.length;
  } catch {
    return 0;
  }
}

export function _resetDismissForTests() {
  loading = null;
}
