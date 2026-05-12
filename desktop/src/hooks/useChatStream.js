import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

const DELTA_FLUSH_MS = 50;
// Tools that finish faster than this snap visually; floor it for legibility.
const MIN_TOOL_RUNNING_MS = 280;

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

  const deltaBufferRef = useRef({ assistant: "", reasoning: "" });
  const deltaFlushScheduledRef = useRef(false);
  const deltaFlushTimerRef = useRef(null);

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

  useEffect(() => {
    const off = listen("chat-event", (event) => {
      const p = event.payload;
      if (p.request_id && p.request_id !== activeRequestIdRef.current) return;
      if (p.kind === "tool_start") {
        setPendingTurn((prev) =>
          prev
            ? {
                ...prev,
                tools: [
                  ...prev.tools,
                  {
                    tool_id: p.tool_id,
                    name: p.name,
                    preview: p.preview,
                    args: p.args,
                    states: [],
                    output: "",
                    ok: null,
                    startedAt: Date.now(),
                  },
                ],
              }
            : prev,
        );
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
  }, [scheduleDeltaFlush, setSessionData, setView, setRewriteDraft, reloadRef, notify]);

  return { pendingTurn, setPendingTurn, activeRequestIdRef };
}
