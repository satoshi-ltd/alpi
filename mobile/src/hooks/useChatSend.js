import { useCallback, useEffect, useRef, useState } from 'react';

import { useEndpoint } from '../lib/EndpointContext';

let _seq = 0;
function nextRequestId() {
  _seq += 1;
  return `m-${Date.now().toString(36)}-${_seq.toString(36)}`;
}

// Watchdog: 15s without frames triggers sidecar replay (Tailscale "open socket, no bytes" case). Daemon heartbeat is 5s — 15s = 3 missed beats.
const STALL_THRESHOLD_MS = 15000;
const STALL_POLL_INTERVAL_MS = 2500;

export function useChatSend({ profile, sessionId, onCompleted }) {
  const { call, callStream } = useEndpoint();
  const [pendingTurn, setPendingTurn] = useState(null);
  const handleRef = useRef(null);
  const requestIdRef = useRef(null);
  // assistant_delta arrives ~30-80/s; rAF buffer caps re-renders at ≤60Hz.
  const deltaBufRef = useRef('');
  const rafRef = useRef(null);
  // Last frame timestamp (live or recovered) — watchdog pivot.
  const lastFrameAtRef = useRef(0);
  const watchdogTimerRef = useRef(null);
  const replayInFlightRef = useRef(false);

  const onCompletedRef = useRef(onCompleted);
  useEffect(() => {
    onCompletedRef.current = onCompleted;
  }, [onCompleted]);

  useEffect(
    () => () => {
      // detach() not cancel() — unmount must NOT interrupt long-running daemon tools.
      handleRef.current?.detach?.();
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      if (watchdogTimerRef.current) clearInterval(watchdogTimerRef.current);
    },
    [],
  );

  const flushDeltas = useCallback(() => {
    rafRef.current = null;
    const chunk = deltaBufRef.current;
    if (!chunk) return;
    deltaBufRef.current = '';
    setPendingTurn((cur) =>
      cur ? { ...cur, assistant: (cur.assistant ?? '') + chunk } : cur,
    );
  }, []);

  const cancel = useCallback(() => {
    handleRef.current?.cancel?.();
    handleRef.current = null;
    requestIdRef.current = null;
    deltaBufRef.current = '';
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (watchdogTimerRef.current) {
      clearInterval(watchdogTimerRef.current);
      watchdogTimerRef.current = null;
    }
    setPendingTurn(null);
  }, []);

  const send = useCallback(
    (text, options = {}) => {
      const trimmed = (text ?? '').trim();
      const attachments = options.attachments?.length ? options.attachments : null;
      if ((!trimmed && !attachments) || !profile) return null;
      handleRef.current?.cancel?.();
      deltaBufRef.current = '';
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      const requestId = nextRequestId();
      requestIdRef.current = requestId;
      lastFrameAtRef.current = Date.now();
      if (watchdogTimerRef.current) clearInterval(watchdogTimerRef.current);
      setPendingTurn({
        at: Math.floor(Date.now() / 1000),
        user: trimmed,
        assistant: '',
        tools: [],
        pending: true,
        attachments: attachments ?? undefined,
      });
      const params = {
        profile,
        text: trimmed,
        request_id: requestId,
      };
      if (sessionId) params.session_id = sessionId;
      if (options.model) params.model = options.model;
      if (attachments) {
        params.attachments = attachments.map((a) => ({ path: a.path, name: a.name, mime: a.mime }));
      }
      if (Number.isInteger(options.rewriteFromTurn)) {
        params.rewrite_from_turn = options.rewriteFromTurn;
      }

      // Daemon mints session_id for new threads — surface via onCompleted so caller pins it before next send.
      let streamSessionId = sessionId ?? null;

      const applyFrame = (frame) => {
        const event = frame?.event;
        if (!event) return;
        lastFrameAtRef.current = Date.now();
        if (frame.session_id) streamSessionId = frame.session_id;
        if (event === 'session_start') {
          setPendingTurn((cur) =>
            cur ? { ...cur, sessionId: streamSessionId } : cur,
          );
          return;
        }
        if (event === 'assistant_delta') {
          deltaBufRef.current += frame.text ?? '';
          if (rafRef.current == null) {
            rafRef.current = requestAnimationFrame(flushDeltas);
          }
        } else if (event === 'tool_start') {
          setPendingTurn((cur) => {
            if (!cur) return cur;
            const tools = [...(cur.tools ?? [])];
            const existing = tools.findIndex((t) => t.tool_id === frame.tool_id);
            const next = {
              tool_id: frame.tool_id ?? frame.name,
              name: frame.name,
              args: frame.args ?? frame.preview,
              ok: null,
            };
            if (existing >= 0) tools[existing] = { ...tools[existing], ...next };
            else tools.push(next);
            return { ...cur, tools };
          });
        } else if (event === 'tool_state') {
          setPendingTurn((cur) => {
            if (!cur) return cur;
            const tools = (cur.tools ?? []).map((t) =>
              t.tool_id === frame.tool_id
                ? { ...t, ok: frame.ok ?? t.ok, text: frame.text }
                : t,
            );
            return { ...cur, tools };
          });
        } else if (event === 'tool_end') {
          setPendingTurn((cur) => {
            if (!cur) return cur;
            const tools = (cur.tools ?? []).map((t) =>
              t.tool_id === frame.tool_id
                ? { ...t, ok: frame.ok ?? true, output: frame.output }
                : t,
            );
            return { ...cur, tools };
          });
        } else if (event === 'reply') {
          deltaBufRef.current = '';
          setPendingTurn((cur) =>
            cur ? { ...cur, assistant: frame.text ?? cur.assistant ?? '' } : cur,
          );
        }
      };

      // Rebuild pendingTurn from sidecar (host.chat.events_since seq=0). Reset state first — daemon returns the FULL turn, would double-apply over live-stream text otherwise.
      const tryRecoverFromSidecar = async () => {
        if (!streamSessionId || !profile) return false;
        try {
          const replay = await call('host.chat.events_since', {
            profile,
            session_id: streamSessionId,
            after_seq: 0,
            limit: 1000,
          });
          const records = Array.isArray(replay?.events) ? replay.events : [];
          // Empty sidecar → bail, keep partial preview (don't wipe what live stream already showed).
          if (records.length === 0) return false;
          deltaBufRef.current = '';
          if (rafRef.current) {
            cancelAnimationFrame(rafRef.current);
            rafRef.current = null;
          }
          setPendingTurn((cur) =>
            cur ? { ...cur, assistant: '', tools: [], error: null } : cur,
          );
          let sawDone = false;
          for (const rec of records) {
            const f = rec?.frame ?? rec;
            applyFrame(f);
            if (f?.event === 'done') sawDone = true;
          }
          flushDeltas();
          if (!sawDone) return false;
          if (watchdogTimerRef.current) {
            clearInterval(watchdogTimerRef.current);
            watchdogTimerRef.current = null;
          }
          handleRef.current?.cancel?.();
          requestIdRef.current = null;
          handleRef.current = null;
          try {
            await onCompletedRef.current?.({
              ok: true,
              sessionId: streamSessionId,
              recovered: true,
            });
          } catch { /* */ }
          setPendingTurn(null);
          return true;
        } catch {
          return false;
        }
      };

      watchdogTimerRef.current = setInterval(() => {
        if (requestIdRef.current !== requestId) return;
        if (replayInFlightRef.current) return;
        const silent = Date.now() - (lastFrameAtRef.current || 0);
        if (silent < STALL_THRESHOLD_MS) return;
        replayInFlightRef.current = true;
        tryRecoverFromSidecar()
          .then((recovered) => {
            if (recovered && watchdogTimerRef.current) {
              clearInterval(watchdogTimerRef.current);
              watchdogTimerRef.current = null;
            }
          })
          .finally(() => {
            replayInFlightRef.current = false;
            lastFrameAtRef.current = Date.now();  // back off the watchdog after one attempt
          });
      }, STALL_POLL_INTERVAL_MS);

      const handle = callStream(params.method ?? 'host.chat.send', params, {
        cancelMethod: 'host.chat.cancel',
        // Daemon emit() in alpi/host/chat.py: tool_start | tool_state | tool_end | assistant_delta | reply | done | heartbeat | error | interrupted | reasoning_delta | auto_compact.
        onFrame: (frame) => {
          if (requestIdRef.current !== requestId) return;
          applyFrame(frame);
        },
        onDone: async () => {
          if (requestIdRef.current !== requestId) return;
          if (rafRef.current) {
            cancelAnimationFrame(rafRef.current);
            rafRef.current = null;
          }
          flushDeltas();
          if (watchdogTimerRef.current) {
            clearInterval(watchdogTimerRef.current);
            watchdogTimerRef.current = null;
          }
          requestIdRef.current = null;
          handleRef.current = null;
          try {
            await onCompletedRef.current?.({ ok: true, sessionId: streamSessionId });
          } catch { /* */ }
          setPendingTurn(null);
        },
        onError: async (err) => {
          if (requestIdRef.current !== requestId) return;
          const recovered = await tryRecoverFromSidecar();
          if (recovered) return;
          if (rafRef.current) {
            cancelAnimationFrame(rafRef.current);
            rafRef.current = null;
          }
          if (watchdogTimerRef.current) {
            clearInterval(watchdogTimerRef.current);
            watchdogTimerRef.current = null;
          }
          flushDeltas();
          requestIdRef.current = null;
          handleRef.current = null;
          setPendingTurn((cur) => (cur ? { ...cur, error: String(err?.message ?? err), pending: false } : null));
          try {
            const ret = onCompletedRef.current?.({ ok: false, error: err });
            if (ret && typeof ret.then === 'function') ret.catch(() => {});
          } catch { /* */ }
        },
      });
      handleRef.current = handle;
      return requestId;
    },
    [call, callStream, profile, sessionId, flushDeltas],
  );

  return { send, cancel, pendingTurn, isStreaming: !!pendingTurn?.pending };
}
