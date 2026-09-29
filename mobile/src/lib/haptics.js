let loading = null;

function load() {
  loading ??= import('expo-haptics').catch(() => null);
  return loading;
}

export async function tapFeedback() {
  const h = await load();
  try {
    await h?.selectionAsync?.();
  } catch {
    return;
  }
}

export async function warnFeedback() {
  const h = await load();
  try {
    await h?.notificationAsync?.(h.NotificationFeedbackType?.Warning ?? 'warning');
  } catch {
    return;
  }
}

export function _resetHapticsForTests() {
  loading = null;
}
