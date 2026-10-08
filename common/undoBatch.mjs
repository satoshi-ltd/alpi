export const UNDO_WINDOW_MS = 5000;

export function deletedMessage(count, title) {
  return count > 1 ? `Deleted ${count} notifications` : `Deleted “${title}”`;
}

export function createUndoBatch({ commit, delayMs = UNDO_WINDOW_MS } = {}) {
  let entries = new Map();
  let timer = null;
  let paused = false;
  let windowMs = delayMs;

  const disarm = () => {
    if (timer === null) return;
    clearTimeout(timer);
    timer = null;
  };

  const take = () => {
    disarm();
    paused = false;
    const batch = Array.from(entries.values());
    entries = new Map();
    return batch;
  };

  // Re-arming spends the full window again, so a paused toast and its pending deletes always expire together.
  const arm = () => {
    disarm();
    if (entries.size === 0 || paused) return;
    timer = setTimeout(() => {
      timer = null;
      commit?.(take());
    }, windowMs);
  };

  return {
    add(key, payload, options) {
      windowMs = options?.delayMs ?? delayMs;
      entries.set(key, payload);
      arm();
      return entries.size;
    },
    keys: () => Array.from(entries.keys()),
    size: () => entries.size,
    pause() {
      paused = true;
      disarm();
    },
    resume() {
      paused = false;
      arm();
    },
    undoAll: take,
  };
}
