import { createContext, useCallback, useContext, useEffect, useMemo, useRef } from 'react';
import { AppState } from 'react-native';

import { useEndpoint } from '../lib/EndpointContext';

const EventsContext = createContext(null);

const RECONNECT_MIN_MS = 1000;
const RECONNECT_MAX_MS = 30000;
// Daemon pings every 25s — a stream silent past three pings is a half-dead link (Tailscale drop without RST), not a quiet daemon.
const STALE_STREAM_MS = 75000;
const WATCHDOG_TICK_MS = 20000;
const RESUME_STALE_MS = 30000;

export function EventsProvider({ children }) {
  const { endpoint, call, callStream } = useEndpoint();
  const listenersRef = useRef(new Set());
  // seq is the canonical backfill pivot; wall-clock `at` is informational only (NTP skew, suspend/resume).
  const lastSeqRef = useRef(0);
  const seenSeqsRef = useRef(new Set());

  const fanOut = useCallback((payload) => {
    const seq = typeof payload?.seq === 'number' ? payload.seq : null;
    if (seq !== null) {
      if (seenSeqsRef.current.has(seq)) return;
      seenSeqsRef.current.add(seq);
      // Cap at 1024 to bound memory while preserving live↔replay dedupe overlap.
      if (seenSeqsRef.current.size > 1024) {
        const arr = Array.from(seenSeqsRef.current);
        seenSeqsRef.current = new Set(arr.slice(arr.length - 512));
      }
      if (seq > lastSeqRef.current) lastSeqRef.current = seq;
    }
    for (const fn of listenersRef.current) {
      try { fn(payload); } catch { /* */ }
    }
  }, []);

  useEffect(() => {
    if (!endpoint) return undefined;
    // seq is per-daemon — endpoint swap invalidates the cursor.
    lastSeqRef.current = 0;
    seenSeqsRef.current = new Set();
    let cancelled = false;
    let attempt = 0;
    let handle = null;
    let retryTimer = null;

    const scheduleRetry = () => {
      if (cancelled) return;
      const delay = Math.min(RECONNECT_MAX_MS, RECONNECT_MIN_MS * 2 ** Math.min(attempt, 5));
      attempt += 1;
      retryTimer = setTimeout(connect, delay);
    };

    const backfill = async () => {
      if (lastSeqRef.current <= 0) return;
      try {
        const res = await call('host.events.history', {
          after_seq: lastSeqRef.current,
          limit: 200,
        });
        // Stale-after-swap guard: post-await events belong to the old daemon's seq space; must not fanOut.
        if (cancelled) return;
        const items = res?.events ?? [];
        for (const it of items) {
          if (!it?.event) continue;
          fanOut({
            event: it.event,
            data: it.data ?? {},
            at: typeof it.at === 'number' ? it.at : Date.now() / 1000,
            seq: typeof it.seq === 'number' ? it.seq : null,
          });
        }
        if (typeof res?.next_seq === 'number' && res.next_seq > lastSeqRef.current) {
          lastSeqRef.current = res.next_seq;
        }
      } catch { /* */ }
    };

    let lastFrameAt = Date.now();

    const connect = () => {
      if (cancelled) return;
      handle = callStream(
        'host.events.subscribe',
        {},
        {
          onFrame: (frame) => {
            if (cancelled) return;
            lastFrameAt = Date.now();
            const event = frame?.event;
            if (!event) return;
            // `subscribed` handshake reply carries the daemon's seq cursor — anchor head on first connect, else backfill the gap.
            if (event === 'subscribed') {
              attempt = 0;
              const anchor = typeof frame.next_seq === 'number' ? frame.next_seq : 0;
              if (lastSeqRef.current === 0 && anchor > 0) {
                lastSeqRef.current = anchor;
              } else {
                backfill();
              }
              return;
            }
            // 'ping' is the daemon's stream keepalive — transport-level, never fans out.
            if (event === 'ping') return;
            if (event === 'done' || event === 'error' || event === 'interrupted') return;
            const at = typeof frame.at === 'number' ? frame.at : Date.now() / 1000;
            const seq = typeof frame.seq === 'number' ? frame.seq : null;
            fanOut({ event, data: frame.data ?? {}, at, seq });
          },
          onError: () => {
            if (cancelled) return;
            handle = null;
            scheduleRetry();
          },
          onDone: () => {
            if (cancelled) return;
            handle = null;
            scheduleRetry();
          },
        },
      );
    };

    const forceReconnect = () => {
      if (cancelled) return;
      lastFrameAt = Date.now();
      if (retryTimer) {
        clearTimeout(retryTimer);
        retryTimer = null;
      }
      handle?.cancel?.();
      handle = null;
      attempt = 0;
      connect();
    };

    const watchdog = setInterval(() => {
      if (cancelled || !handle) return;
      if (Date.now() - lastFrameAt > STALE_STREAM_MS) forceReconnect();
    }, WATCHDOG_TICK_MS);

    const appStateSub = AppState.addEventListener('change', (state) => {
      if (cancelled || state !== 'active') return;
      // Resume from background: the OS may have killed the socket without an error — reconnect now instead of waiting out the watchdog.
      if (Date.now() - lastFrameAt > RESUME_STALE_MS) forceReconnect();
    });

    connect();

    return () => {
      cancelled = true;
      clearInterval(watchdog);
      appStateSub?.remove?.();
      if (retryTimer) clearTimeout(retryTimer);
      handle?.cancel?.();
    };
  }, [endpoint, call, callStream, fanOut]);

  const subscribe = useCallback((fn) => {
    listenersRef.current.add(fn);
    return () => listenersRef.current.delete(fn);
  }, []);

  const value = useMemo(() => ({ subscribe }), [subscribe]);
  return (
    <EventsContext.Provider value={value}>{children}</EventsContext.Provider>
  );
}

export function useEvents() {
  return useContext(EventsContext) ?? { subscribe: () => () => {} };
}

// fnRef pattern lets callers pass inline arrows without re-subscribing every render.
export function useEventEffect(kinds, fn) {
  const { subscribe } = useEvents();
  const list = Array.isArray(kinds) ? kinds : [kinds];
  const key = list.join(',');
  const fnRef = useRef(fn);
  useEffect(() => {
    fnRef.current = fn;
  }, [fn]);
  useEffect(() => {
    const unsub = subscribe((ev) => {
      if (list.includes(ev.event)) fnRef.current?.(ev);
    });
    return unsub;
  }, [subscribe, key]); // eslint-disable-line react-hooks/exhaustive-deps
}
