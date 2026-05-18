import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

const DELTA_FLUSH_MS = 50;
// Tools that finish faster than this snap visually; floor it for legibility.
const MIN_TOOL_RUNNING_MS = 280;
// If no chat-event arrives for this long while a turn is in flight, assume the host-plane stream socket died and replay the sidecar.
const STALL_THRESHOLD_MS = 10_000;
const STALL_POLL_INTERVAL_MS = 2_000;

export function useChatStream({
  setSessionData,
  setView,
  setRewriteDraft,
  reloadRef,
  notify,
}) {
  const [pendingTurn, setPendingTurn] = useState(null);

  // Drop late frames from an interrupted turn so they don't mutate the new pendingTurn.
  const activeRequestIdRef = useRef(null);
  const pendingTurnRef = useRef(null);
  const lastEventAtRef = useRef(0);
  const replayingRef = useRef(false);

  const deltaBufferRef = useRef({ assistant: "", reasoning: "" });
  const deltaFlushScheduledRef = useRef(false);
  const deltaFlushTimerRef = useRef(null);

  const markActivity = useCallback(() => {
    lastEventAtRef.current = Date.now();
  }, []);

  useEffect(() => {
    const prev = pendingTurnRef.current;
    pendingTurnRef.current = pendingTurn;
    // Fresh turn: arm the watchdog from now so the previous turn's silence doesn't trip an immediate replay.
    if (pendingTurn && pendingTurn.requestId !== prev?.requestId) {
      lastEventAtRef.current = Date.now();
    }
  }, [pendingTurn]);

  const flushDeltas = useCallback(() => {
    deltaFlushScheduledRef.current = false;
    const { assistant, reasoning } = deltaBufferRef.current;
    if (!assistant && !reasoning) return;
    deltaBufferRef.current = { assistant: "", reasoning: "" };
    setPendingTurn((prev) => {
      if (!prev) return prev;
      const next = { ...prev };
      if (assistant)
        next.assistantPreview = (prev.assistantPreview ?? "") + assistant;
      if (reasoning)
        next.reasoningPreview = (prev.reasoningPreview ?? "") + reasoning;
      return next;
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
    };
  }, []);

  // Rebuild pendingTurn state from the persisted sidecar — used when the live stream goes silent.
  const applyReplayedEvents = useCallback((events) => {
    let sawDone = false;
    let finalSessionId = null;
    let nextTools = [];
    let assistant = "";
    let reasoning = "";
    let errorText = null;

    for (const rec of events) {
      const f = rec.frame ?? {};
      const kind = f.event;
      if (kind === "tool_start") {
        const existing = nextTools.findIndex((t) => t.tool_id === f.tool_id);
        const entry = {
          tool_id: f.tool_id,
          name: f.name,
          preview: f.preview,
          args: f.args,
          states: existing >= 0 ? nextTools[existing].states : [],
          output: existing >= 0 ? nextTools[existing].output : "",
          ok: null,
          startedAt: existing >= 0 ? nextTools[existing].startedAt : Date.now(),
        };
        if (existing >= 0) nextTools[existing] = entry;
        else nextTools.push(entry);
      } else if (kind === "tool_state") {
        for (let i = nextTools.length - 1; i >= 0; i--) {
          if (nextTools[i].tool_id === f.tool_id && nextTools[i].ok === null) {
            nextTools[i] = {
              ...nextTools[i],
              states: [...nextTools[i].states, { text: f.text, ok: f.ok }],
            };
            break;
          }
        }
      } else if (kind === "tool_end") {
        for (let i = nextTools.length - 1; i >= 0; i--) {
          if (nextTools[i].tool_id === f.tool_id && nextTools[i].ok === null) {
            nextTools[i] = { ...nextTools[i], ok: f.ok, output: f.output ?? "" };
            break;
          }
        }
      } else if (kind === "assistant_delta") {
        assistant += f.text ?? "";
      } else if (kind === "reasoning_delta") {
        reasoning += f.text ?? "";
      } else if (kind === "error") {
        errorText = f.text ?? "stream error";
      } else if (kind === "reply") {
        if (f.session_id) finalSessionId = f.session_id;
      } else if (kind === "done") {
        sawDone = true;
        if (f.session_id) finalSessionId = f.session_id;
      }
    }

    setPendingTurn((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        tools: nextTools,
        assistantPreview: assistant || prev.assistantPreview,
        reasoningPreview: reasoning || prev.reasoningPreview,
        error: errorText,
      };
    });

    return { sawDone, finalSessionId };
  }, []);

  const runReplay = useCallback(async () => {
    if (replayingRef.current) return;
    const turn = pendingTurnRef.current;
    if (!turn?.sessionId || !turn?.profile) return;
    replayingRef.current = true;
    const firstAttempt = !turn.didNotifyReconnecting;
    try {
      if (firstAttempt) {
        notify({ message: "Stream went silent — reconnecting…", variant: "info" });
        setPendingTurn((prev) =>
          prev ? { ...prev, didNotifyReconnecting: true } : prev,
        );
      }
      const result = await invoke("chat_events_since", {
        profile: turn.profile,
        sessionId: turn.sessionId,
        afterSeq: 0,
      });
      if (!result?.exists) return;
      const events = Array.isArray(result.events) ? result.events : [];
      // Drop already-buffered deltas — we're rebuilding from disk.
      deltaBufferRef.current = { assistant: "", reasoning: "" };
      const { sawDone, finalSessionId } = applyReplayedEvents(events);
      if (sawDone) {
        notify({ message: "Reconnected — turn recovered from disk", variant: "success" });
        const sid = finalSessionId ?? turn.sessionId;
        try {
          const newData = await invoke("session_detail", {
            profile: turn.profile,
            id: sid,
          });
          setSessionData(newData);
          setRewriteDraft(null);
          setView({ kind: "profile", profile: turn.profile, sessionId: sid });
          reloadRef.current?.();
        } catch (e) {
          notify({ message: String(e), variant: "error" });
        }
        setPendingTurn((prev) => (prev?.error ? prev : null));
      } else {
        // Daemon may still be working — the watchdog will fire again; arm the clock so we don't spam-replay.
        lastEventAtRef.current = Date.now();
      }
    } catch (e) {
      notify({ message: `reconnect failed: ${e}`, variant: "error" });
    } finally {
      replayingRef.current = false;
    }
  }, [applyReplayedEvents, notify, reloadRef, setRewriteDraft, setSessionData, setView]);

  // Stall watchdog — polls every STALL_POLL_INTERVAL_MS while a turn is pending.
  useEffect(() => {
    if (!pendingTurn) return undefined;
    const id = setInterval(() => {
      const turn = pendingTurnRef.current;
      if (!turn) return;
      if (replayingRef.current) return;
      if (!turn.sessionId) return; // new sessions can't replay; no sidecar key yet
      const silentFor = Date.now() - (lastEventAtRef.current || 0);
      if (silentFor >= STALL_THRESHOLD_MS) {
        runReplay();
      }
    }, STALL_POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [pendingTurn, runReplay]);

  useEffect(() => {
    const off = listen("chat-event", (event) => {
      const p = event.payload;
      if (p.request_id && p.request_id !== activeRequestIdRef.current) return;
      markActivity();
      if (p.kind === "heartbeat") {
        return; // keepalive only — daemon proving the loop is alive
      }
      if (p.kind === "tool_start") {
        setPendingTurn((prev) => {
          if (!prev) return prev;
          const existing = prev.tools.findIndex((t) => t.tool_id === p.tool_id);
          const entry = {
            tool_id: p.tool_id,
            name: p.name,
            preview: p.preview,
            args: p.args,
            states: existing >= 0 ? prev.tools[existing].states : [],
            output: existing >= 0 ? prev.tools[existing].output : "",
            ok: null,
            startedAt: existing >= 0 ? prev.tools[existing].startedAt : Date.now(),
          };
          const tools = existing >= 0
            ? prev.tools.map((t, i) => (i === existing ? entry : t))
            : [...prev.tools, entry];
          return { ...prev, tools };
        });
      } else if (p.kind === "tool_state") {
        setPendingTurn((prev) => {
          if (!prev) return prev;
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
          setPendingTurn((prev) => {
            if (!prev) return prev;
            const tools = [...prev.tools];
            for (let i = tools.length - 1; i >= 0; i--) {
              if (matchTool(tools[i])) {
                tools[i] = {
                  ...tools[i],
                  ok: p.ok,
                  output: p.output ?? "",
                };
                break;
              }
            }
            return { ...prev, tools };
          });
        }
        setPendingTurn((prev) => {
          if (!prev) return prev;
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
            };
            return { ...prev, tools };
          }
          setTimeout(applyEnd, MIN_TOOL_RUNNING_MS - elapsed);
          return prev;
        });
      } else if (p.kind === "assistant_delta") {
        deltaBufferRef.current.assistant += p.text;
        scheduleDeltaFlush();
      } else if (p.kind === "reasoning_delta") {
        deltaBufferRef.current.reasoning += p.text;
        scheduleDeltaFlush();
      } else if (p.kind === "auto_compact") {
        setPendingTurn((prev) =>
          prev
            ? {
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
              }
            : prev,
        );
      } else if (p.kind === "error") {
        setPendingTurn((prev) => (prev ? { ...prev, error: p.text } : prev));
      } else if (p.kind === "reply") {
        setPendingTurn((prev) => {
          if (!prev || !p.session_id) return prev;
          const profileName = prev.profile;
          invoke("session_detail", {
            profile: profileName,
            id: p.session_id,
          })
            .then((newData) => {
              setSessionData(newData);
              setRewriteDraft(null);
              setView({
                kind: "profile",
                profile: profileName,
                sessionId: p.session_id,
              });
              reloadRef.current?.();
            })
            .catch((e) => notify({ message: String(e), variant: "error" }));
          return prev;
        });
      } else if (p.kind === "done") {
        // Drop buffered deltas — the persisted session already has them.
        deltaBufferRef.current = { assistant: "", reasoning: "" };
        setPendingTurn((prev) => (prev?.error ? prev : null));
      }
    });
    return () => {
      off.then((fn) => fn());
    };
  }, [markActivity, scheduleDeltaFlush, setSessionData, setView, setRewriteDraft, reloadRef, notify]);

  return { pendingTurn, setPendingTurn, activeRequestIdRef };
}
