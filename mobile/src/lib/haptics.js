let loading = null;

function load() {
  loading ??= import('expo-haptics').catch(() => null);
  return loading;
}

async function play(run) {
  const h = await load();
  if (!h) return;
  try {
    await run(h);
  } catch {
    return;
  }
}

export function tap() {
  return play((h) => h.impactAsync?.(h.ImpactFeedbackStyle?.Light ?? 'light'));
}

export function selection() {
  return play((h) => h.selectionAsync?.());
}

export function warning() {
  return play((h) => h.notificationAsync?.(h.NotificationFeedbackType?.Warning ?? 'warning'));
}

export function success() {
  return play((h) => h.notificationAsync?.(h.NotificationFeedbackType?.Success ?? 'success'));
}

export function _resetHapticsForTests() {
  loading = null;
}
