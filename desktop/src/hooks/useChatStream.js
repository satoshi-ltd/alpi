import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { safeUnlisten } from "../lib/tauri-listen.js";
import { fetchFullSession } from "../lib/session-fetch.js";
import { saveCachedSession } from "../lib/session-cache.js";
import { reconstructFromEvents } from "../lib/reconstructTurn.js";

const DELTA_FLUSH_MS = 50;
// Tools that finish faster than this snap visually; floor it for legibility.
const MIN_TOOL_RUNNING_MS = 280;
// If no chat-event arrives for this long while a turn is in flight, assume the host-plane stream socket died and replay the sidecar.
const STALL_THRESHOLD_MS = 10_000;
const STALL_POLL_INTERVAL_MS = 2_000;
const TURN_SETTLE_TIMEOUT_MS = 30_000;

export function useChatStream({
  setSessionData,
  setView,
  setRewriteDraft,
  reloadRef,
  notify,
  connectionOnlineRef,
  activeConnectionIdRef,
  sessionDataRef,
}) {
  // request_id -> turn. Many chats stream at once; each frame carries its request_id, so a turn never leaks into another chat.
  const [pendingTurns, setPendingTurns] = useState({});
  const pendingTurnsRef = useRef({});
  // request_id -> { lastEventAt, replaying }. Hot per-turn clocks kept off React state so frames don't re-render for timing alone.
  const turnMetaRef = useRef({});
  const deltaBufferRef = useRef({});
  const deltaFlushScheduledRef = useRef(false);
  const deltaFlushTimerRef = useRef(null);
  // { requestId, timer } entries — cleared per-turn so one turn's done/cancel can't drop another's deferred tool_end.
  const toolEndTimersRef = useRef(new Set());
  const settlementsRef = useRef(new Map());

  useEffect(() => {
    pendingTurnsRef.current = pendingTurns;
  }, [pendingTurns]);

  const fetchFinishedSession = useCallback(async (turn, sid) => {
    const current = sessionDataRef?.current;
    const known = current?.id === sid ? current : null;
    const data = await fetchFullSession(turn.profile, sid, { known });
    // Cache under the turn's own connection — resolving the active one here would poison another daemon's cache after a mid-fetch switch.
    saveCachedSession(turn.connectionId ?? null, turn.profile, sid, data);
    return data;
  }, [sessionDataRef]);

  const isActiveConnection = useCallback(
    (turn) =>
      !activeConnectionIdRef ||
      (turn.connectionId ?? null) === (activeConnectionIdRef.current ?? null),
    [activeConnectionIdRef],
  );

  const updateTurn = useCallback((requestId, updater) => {
    setPendingTurns((prev) => {
      const cur = prev[requestId];
      if (cur === undefined) return prev;
      const next = updater(cur);
      if (next === cur) return prev;
      if (next == null) {
        const { [requestId]: _omit, ...rest } = prev;
        return rest;
      }
      return { ...prev, [requestId]: next };
    });
  }, []);

  const dropTurnTimers = useCallback((requestId) => {
    for (const entry of [...toolEndTimersRef.current]) {
      if (entry.requestId === requestId) {
        clearTimeout(entry.timer);
        toolEndTimersRef.current.delete(entry);
      }
    }
    const settlement = settlementsRef.current.get(requestId);
    if (settlement !== undefined) {
      clearTimeout(settlement.timer);
      settlementsRef.current.delete(requestId);
    }
  }, []);

  const markActivity = useCallback((requestId) => {
    const meta = turnMetaRef.current[requestId];
    if (meta) meta.lastEventAt = Date.now();
  }, []);

  // Add a turn, superseding any prior turn for the SAME chat — an existing session, or the single blank-composer slot (launchSessionId null); other chats keep streaming.
  const startTurn = useCallback((turn) => {
    const rid = turn.requestId;
    dropTurnTimers(rid);
    turnMetaRef.current[rid] = { lastEventAt: Date.now(), replaying: false };
    deltaBufferRef.current[rid] = { assistant: "", reasoning: "" };
    const slot = turn.launchSessionId ?? null;
    setPendingTurns((prev) => {
      const next = {};
      for (const [k, t] of Object.entries(prev)) {
        const sameChat =
          (t.connectionId ?? null) === (turn.connectionId ?? null) &&
          t.profile === turn.profile &&
          (slot != null
            ? (t.sessionId ?? t.launchSessionId ?? null) === slot
            : (t.launchSessionId ?? null) === null);
        if (sameChat) {
          delete turnMetaRef.current[k];
          delete deltaBufferRef.current[k];
          dropTurnTimers(k);
          continue;
        }
        next[k] = t;
      }
      next[rid] = turn;
      return next;
    });
  }, [dropTurnTimers]);

  const removeTurn = useCallback((requestId) => {
    delete turnMetaRef.current[requestId];
    delete deltaBufferRef.current[requestId];
    dropTurnTimers(requestId);
    setPendingTurns((prev) => {
      if (prev[requestId] === undefined) return prev;
      const { [requestId]: _omit, ...rest } = prev;
      return rest;
    });
  }, [dropTurnTimers]);

  const clearTurnsForConnection = useCallback((connectionId) => {
    const cid = connectionId ?? null;
    setPendingTurns((prev) => {
      let changed = false;
      const next = {};
      for (const [rid, t] of Object.entries(prev)) {
        if ((t.connectionId ?? null) === cid) {
          delete turnMetaRef.current[rid];
          delete deltaBufferRef.current[rid];
          dropTurnTimers(rid);
          changed = true;
          continue;
        }
        next[rid] = t;
      }
      return changed ? next : prev;
    });
  }, [dropTurnTimers]);

  const detachNewChatTurns = useCallback((connectionId) => {
    const cid = connectionId ?? null;
    setPendingTurns((prev) => {
      let changed = false;
      const next = { ...prev };
      for (const [rid, t] of Object.entries(prev)) {
        if ((t.connectionId ?? null) === cid && (t.launchSessionId ?? null) === null) {
          next[rid] = { ...t, launchSessionId: t.sessionId ?? t.requestId };
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, []);

  const flushDeltas = useCallback(() => {
    deltaFlushScheduledRef.current = false;
    const buffers = deltaBufferRef.current;
    const updates = [];
    for (const rid of Object.keys(buffers)) {
      const { assistant, reasoning } = buffers[rid];
      if (assistant || reasoning) updates.push([rid, assistant, reasoning]);
      buffers[rid] = { assistant: "", reasoning: "" };
    }
    if (!updates.length) return;
    setPendingTurns((prev) => {
      let changed = false;
      const next = { ...prev };
      for (const [rid, assistant, reasoning] of updates) {
        const cur = prev[rid];
        if (!cur) continue;
        const t = { ...cur };
        if (assistant) t.assistantPreview = (cur.assistantPreview ?? "") + assistant;
        if (reasoning) t.reasoningPreview = (cur.reasoningPreview ?? "") + reasoning;
        next[rid] = t;
        changed = true;
      }
      return changed ? next : prev;
    });
  }, []);

  const scheduleDeltaFlush = useCallback(() => {
    if (deltaFlushScheduledRef.current) return;
    deltaFlushScheduledRef.current = true;
    deltaFlushTimerRef.current = setTimeout(flushDeltas, DELTA_FLUSH_MS);
  }, [flushDeltas]);

  useEffect(() => {
    return () => {
      if (deltaFlushTimerRef.current) clearTimeout(deltaFlushTimerRef.current);
      for (const entry of toolEndTimersRef.current) clearTimeout(entry.timer);
      toolEndTimersRef.current.clear();
      for (const settlement of settlementsRef.current.values()) clearTimeout(settlement.timer);
      settlementsRef.current.clear();
    };
  }, []);

  // Navigate/refresh the view only when the finished turn is the one on screen — a background turn completing must not yank the open chat.
  const finishTurnView = useCallback((turn, sid, newData) => {
    if (!isActiveConnection(turn)) return;
    setView((cur) => {
      const isProfile = cur?.kind === "profile" && cur.profile === turn.profile;
      const foregroundExisting = isProfile && (cur.sessionId ?? null) === sid;
      const foregroundNewChat =
        isProfile && (cur.sessionId ?? null) === null && (turn.launchSessionId ?? null) === null;
      if (foregroundExisting || foregroundNewChat) {
        setRewriteDraft(null);
        setSessionData(newData);
        return { kind: "profile", profile: turn.profile, sessionId: sid };
      }
      return cur;
    });
    reloadRef.current?.();
  }, [setView, setRewriteDraft, setSessionData, reloadRef, isActiveConnection]);

  const loadFinishedTurn = useCallback((turn, sid) =>
    fetchFinishedSession(turn, sid)
      .then((newData) => {
        finishTurnView(turn, sid, newData);
        return true;
      })
      .catch((e) => {
        notify({ message: String(e), variant: "error" });
        return false;
      }), [fetchFinishedSession, finishTurnView, notify]);

  const dropSettledTurn = useCallback((requestId) => {
    setPendingTurns((prev) => {
      const cur = prev[requestId];
      if (cur === undefined) return prev;
      if (cur.error) {
        // keep an errored turn on screen
        return cur.settling ? { ...prev, [requestId]: { ...cur, settling: false } } : prev;
      }
      const { [requestId]: _omit, ...rest } = prev;
      return rest;
    });
  }, []);

  const settleTurn = useCallback((requestId, load) => {
    if (settlementsRef.current.has(requestId)) return;
    const settlement = { timer: null };
    const close = () => {
      if (settlementsRef.current.get(requestId) !== settlement) return false;
      clearTimeout(settlement.timer);
      settlementsRef.current.delete(requestId);
      return true;
    };
    settlement.timer = setTimeout(() => {
      if (close()) dropSettledTurn(requestId);
    }, TURN_SETTLE_TIMEOUT_MS);
    settlementsRef.current.set(requestId, settlement);
    updateTurn(requestId, (cur) => (cur.settling ? cur : { ...cur, settling: true }));
    load.then(
      () => {
        if (close()) dropSettledTurn(requestId);
      },
      () => {
        if (close()) dropSettledTurn(requestId);
      },
    );
  }, [dropSettledTurn, updateTurn]);

  // Rebuild a turn's state from the persisted sidecar — used when its live stream goes silent.
  const applyReplayedEvents = useCallback((requestId, events) => {
    const { tools, assistant, reasoning, error, sawDone, finalSessionId } = reconstructFromEvents(events);
    updateTurn(requestId, (prev) => ({
      ...prev,
      tools,
      assistantPreview: assistant || prev.assistantPreview,
      reasoningPreview: reasoning || prev.reasoningPreview,
      error,
    }));
    return { sawDone, finalSessionId };
  }, [updateTurn]);

  const runReplay = useCallback(async (requestId) => {
    const meta = turnMetaRef.current[requestId];
    if (!meta || meta.replaying) return;
    const turn = pendingTurnsRef.current[requestId];
    if (!turn?.sessionId || !turn?.profile) return;
    meta.replaying = true;
    const firstAttempt = !turn.didNotifyReconnecting;
    try {
      if (firstAttempt) {
        notify({ message: "Stream went silent — reconnecting…", variant: "info" });
        updateTurn(requestId, (prev) =>
          prev ? { ...prev, didNotifyReconnecting: true } : prev,
        );
      }
      const result = await invoke("chat_events_since", {
        profile: turn.profile,
        sessionId: turn.sessionId,
        afterSeq: 0,
      });
      if (!result?.exists) return;
      if (settlementsRef.current.has(requestId)) return;
      const events = Array.isArray(result.events) ? result.events : [];
      deltaBufferRef.current[requestId] = { assistant: "", reasoning: "" };
      const { sawDone, finalSessionId } = applyReplayedEvents(requestId, events);
      if (sawDone) {
        notify({ message: "Reconnected — turn recovered from disk", variant: "success" });
        const sid = finalSessionId ?? turn.sessionId;
        const load = loadFinishedTurn(turn, sid);
        delete turnMetaRef.current[requestId];
        delete deltaBufferRef.current[requestId];
        dropTurnTimers(requestId);
        settleTurn(requestId, load);
      } else {
        meta.lastEventAt = Date.now();
      }
    } catch (e) {
      notify({ message: `reconnect failed: ${e}`, variant: "error" });
    } finally {
      const m = turnMetaRef.current[requestId];
      if (m) m.replaying = false;
    }
  }, [applyReplayedEvents, dropTurnTimers, loadFinishedTurn, notify, settleTurn, updateTurn]);

  useEffect(() => {
    if (Object.keys(pendingTurns).length === 0) return undefined;
    const id = setInterval(() => {
      if (connectionOnlineRef?.current === false) return;
      const now = Date.now();
      for (const [rid, turn] of Object.entries(pendingTurnsRef.current)) {
        const meta = turnMetaRef.current[rid];
        if (!meta || meta.replaying) continue;
        if (turn.error) continue;
        if (!turn.sessionId) continue;
        if (!isActiveConnection(turn)) continue;
        if (now - (meta.lastEventAt || 0) >= STALL_THRESHOLD_MS) runReplay(rid);
      }
    }, STALL_POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [pendingTurns, runReplay, connectionOnlineRef, isActiveConnection]);

  useEffect(() => {
    let cancelled = false;
    let unlisten = null;
    listen("chat-event", (event) => {
      const p = event.payload;
      const rid = p.request_id;
      if (!rid || pendingTurnsRef.current[rid] === undefined) return;
      if (settlementsRef.current.has(rid)) return;
      markActivity(rid);
      if (p.kind === "heartbeat") {
        return; // keepalive only — daemon proving the loop is alive
      }
      if (p.kind === "session_start") {
        // Pin the sessionId BEFORE any tool/delta arrives so the stall watchdog can replay via host.chat.events_since even if the next frame is lost.
        if (p.session_id) {
          updateTurn(rid, (prev) => ({ ...prev, sessionId: p.session_id, runId: p.run_id ?? prev.runId ?? null }));
        }
        return;
      }
      if (p.kind === "tool_start") {
        const buf = deltaBufferRef.current[rid] ?? { assistant: "", reasoning: "" };
        const pendingProse = buf.assistant;
        const pendingReasoning = buf.reasoning;
        deltaBufferRef.current[rid] = { assistant: "", reasoning: "" };
        updateTurn(rid, (prev) => {
          const existing = prev.tools.findIndex((t) => t.tool_id === p.tool_id);
          const prior = existing >= 0 ? prev.tools[existing] : null;
          const segment = [prev.reasoningPreview, pendingReasoning, `${prev.assistantPreview ?? ""}${pendingProse}`]
            .map((s) => (s ?? "").trim())
            .filter(Boolean)
            .join("\n\n");
          const reasoning = segment || prior?.reasoning;
          const entry = {
            tool_id: p.tool_id,
            name: p.name,
            preview: p.preview,
            args: p.args,
            states: prior ? prior.states : [],
            output: prior ? prior.output : "",
            ok: null,
            startedAt: prior ? prior.startedAt : Date.now(),
            at: prior?.at ?? Date.now() / 1000,
            ...(reasoning ? { reasoning } : {}),
          };
          const tools = existing >= 0
            ? prev.tools.map((t, i) => (i === existing ? entry : t))
            : [...prev.tools, entry];
          return { ...prev, tools, reasoningPreview: "", assistantPreview: "" };
        });
      } else if (p.kind === "tool_state") {
        updateTurn(rid, (prev) => {
          const tools = prev.tools.map((t) =>
            t.tool_id === p.tool_id && t.ok === null
              ? { ...t, states: [...t.states, { text: p.text, ok: p.ok }] }
              : t,
          );
          return { ...prev, tools };
        });
      } else if (p.kind === "tool_end") {
        const matchTool = (t) =>
          (p.tool_id && t.tool_id === p.tool_id) ||
          (!p.tool_id && t.name === p.name && t.ok === null);
        function applyEnd() {
          // Stale fire after the turn ended/cancelled must not resurrect it.
          if (pendingTurnsRef.current[rid] === undefined) return;
          updateTurn(rid, (prev) => {
            const tools = [...prev.tools];
            for (let i = tools.length - 1; i >= 0; i--) {
              if (matchTool(tools[i])) {
                tools[i] = {
                  ...tools[i],
                  ok: p.ok,
                  output: p.output ?? "",
                  duration_s: Math.max(0, (Date.now() - tools[i].startedAt) / 1000),
                };
                break;
              }
            }
            return { ...prev, tools };
          });
        }
        updateTurn(rid, (prev) => {
          let idx = -1;
          for (let i = prev.tools.length - 1; i >= 0; i--) {
            if (matchTool(prev.tools[i])) {
              idx = i;
              break;
            }
          }
          if (idx === -1) return prev;
          const startedAt = prev.tools[idx].startedAt ?? Date.now();
          const elapsed = Date.now() - startedAt;
          if (elapsed >= MIN_TOOL_RUNNING_MS) {
            const tools = [...prev.tools];
            tools[idx] = {
              ...tools[idx],
              ok: p.ok,
              output: p.output ?? "",
              duration_s: elapsed / 1000,
            };
            return { ...prev, tools };
          }
          const entry = { requestId: rid, timer: null };
          entry.timer = setTimeout(() => {
            toolEndTimersRef.current.delete(entry);
            applyEnd();
          }, MIN_TOOL_RUNNING_MS - elapsed);
          toolEndTimersRef.current.add(entry);
          return prev;
        });
      } else if (p.kind === "assistant_delta") {
        const buf = (deltaBufferRef.current[rid] ??= { assistant: "", reasoning: "" });
        buf.assistant += p.text;
        scheduleDeltaFlush();
      } else if (p.kind === "reasoning_delta") {
        const buf = (deltaBufferRef.current[rid] ??= { assistant: "", reasoning: "" });
        buf.reasoning += p.text;
        scheduleDeltaFlush();
      } else if (p.kind === "auto_compact") {
        updateTurn(rid, (prev) => ({
          ...prev,
          tools: [
            ...prev.tools,
            {
              tool_id: `auto-compact-${Date.now()}`,
              name: "auto-compact",
              preview: p.text,
              args: {
                tokens_before: p.tokens_before,
                tokens_after: p.tokens_after,
              },
              states: [],
              output: p.text,
              ok: true,
              startedAt: Date.now(),
            },
          ],
        }));
      } else if (p.kind === "error") {
        updateTurn(rid, (prev) => ({ ...prev, error: p.text }));
      } else if (p.kind === "reply") {
        if (!p.session_id) return;
        const turn = pendingTurnsRef.current[rid];
        if (!turn) return;
        if (!isActiveConnection(turn)) return;
        const sid = p.session_id;
        const load = loadFinishedTurn(turn, sid);
        const meta = turnMetaRef.current[rid];
        if (meta) meta.load = load;
      } else if (p.kind === "done") {
        const turn = pendingTurnsRef.current[rid];
        const started = turnMetaRef.current[rid]?.load ?? null;
        const sid = p.session_id || turn?.sessionId || null;
        const load = started
          ?? (turn && sid && !turn.error && isActiveConnection(turn)
            ? loadFinishedTurn(turn, sid)
            : null);
        delete turnMetaRef.current[rid];
        delete deltaBufferRef.current[rid];
        dropTurnTimers(rid);
        if (load) settleTurn(rid, load);
        else dropSettledTurn(rid);
      }
    })
      .then((fn) => {
        if (cancelled) safeUnlisten(fn);
        else unlisten = fn;
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      safeUnlisten(unlisten);
    };
  }, [markActivity, scheduleDeltaFlush, updateTurn, dropTurnTimers, loadFinishedTurn, settleTurn, dropSettledTurn, isActiveConnection]);

  return { pendingTurns, pendingTurnsRef, startTurn, removeTurn, clearTurnsForConnection, detachNewChatTurns };
}
