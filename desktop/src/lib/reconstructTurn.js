export function reconstructFromEvents(events) {
  let sawDone = false;
  let finalSessionId = null;
  const nextTools = [];
  let assistant = "";
  let reasoning = "";
  let errorText = null;
  let ctxTokens = null;
  let reasonedSeconds = null;
  let reasoningDone = false;
  let spanSeconds = 0;
  for (const rec of events) {
    const f = rec.frame ?? {};
    const kind = f.event;
    if (kind === "session_start") {
      if (f.session_id) finalSessionId = f.session_id;
    } else if (kind === "tool_start") {
      const segment = [reasoning, assistant.trim()].map((s) => (s ?? "").trim()).filter(Boolean).join("\n\n");
      reasoning = "";
      assistant = "";
      reasoningDone = false;
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
        started_at: Number.isFinite(f.started_at) ? f.started_at : (existing >= 0 ? nextTools[existing].started_at ?? null : null),
        at: existing >= 0
          ? nextTools[existing].at
          : Number.isFinite(f.started_at) ? f.started_at : (Number.isFinite(rec.ts) ? rec.ts : Date.now() / 1000),
        ...(segment ? { reasoning: segment } : {}),
        ...(spanSeconds > 0 ? { reasoned_s: spanSeconds } : existing >= 0 && nextTools[existing].reasoned_s ? { reasoned_s: nextTools[existing].reasoned_s } : {}),
      };
      spanSeconds = 0;
      if (existing >= 0) nextTools[existing] = entry;
      else nextTools.push(entry);
    } else if (kind === "tool_state") {
      for (let i = nextTools.length - 1; i >= 0; i--) {
        if (nextTools[i].tool_id === f.tool_id && nextTools[i].ok === null) {
          nextTools[i] = { ...nextTools[i], states: [...nextTools[i].states, { text: f.text, ok: f.ok }] };
          break;
        }
      }
    } else if (kind === "tool_end") {
      const endTs = Number.isFinite(rec.ts) ? rec.ts : Date.now() / 1000;
      for (let i = nextTools.length - 1; i >= 0; i--) {
        if (nextTools[i].tool_id === f.tool_id && nextTools[i].ok === null) {
          nextTools[i] = {
            ...nextTools[i],
            ok: f.ok,
            output: f.output ?? "",
            duration_s: Number.isFinite(f.duration_s) ? f.duration_s : Math.max(0, endTs - (nextTools[i].at ?? endTs)),
          };
          break;
        }
      }
    } else if (kind === "assistant_delta") {
      assistant += f.text ?? "";
    } else if (kind === "reasoning_delta") {
      reasoning += f.text ?? "";
      reasoningDone = false;
    } else if (kind === "reasoning_done") {
      const seconds = Number.isFinite(f.seconds) && f.seconds > 0 ? f.seconds : 0;
      reasonedSeconds = (reasonedSeconds ?? 0) + seconds;
      spanSeconds += seconds;
      reasoningDone = true;
    } else if (kind === "usage" && f.context_tokens > 0) {
      ctxTokens = f.context_tokens;
    } else if (kind === "auto_compact" && f.tokens_after > 0) {
      ctxTokens = f.tokens_after;
    } else if (kind === "error") {
      errorText = f.text ?? "stream error";
    } else if (kind === "reply") {
      if (f.session_id) finalSessionId = f.session_id;
    } else if (kind === "done") {
      sawDone = true;
      if (f.session_id) finalSessionId = f.session_id;
    }
  }
  return { tools: nextTools, assistant, reasoning, error: errorText, sawDone, finalSessionId, ctxTokens, reasonedSeconds, reasoningDone, spanReasonedSeconds: spanSeconds, sawToolStart: nextTools.length > 0 };
}
