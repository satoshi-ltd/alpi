const listeners = new Set();

export function onInboxSignal(fn) {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}

export function signalInbox(connectionId) {
  for (const fn of Array.from(listeners)) {
    try { fn(connectionId); } catch { /* one listener must not starve the rest */ }
  }
}
