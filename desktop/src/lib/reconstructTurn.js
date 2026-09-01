export function reconstructFromEvents(events) {
  let sawDone = false;
  let finalSessionId = null;
  const nextTools = [];
  let assistant = "";
  let reasoning = "";
  let errorText = null;
  let ctxTokens = null;
  for (const rec of events) {
    const f = rec.frame ?? {};
    const kind = f.event;
    if (kind === "session_start") {
      if (f.session_id) finalSessionId = f.session_id;
    } else if (kind === "tool_start") {
      const segment = [reasoning, assistant.trim()].map((s) => (s ?? "").trim()).filter(Boolean).join("\n\n");
      reasoning = "";
      assistant = "";
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
        at: existing >= 0 ? nextTools[existing].at : (Number.isFinite(rec.ts) ? rec.ts : Date.now() / 1000),
        ...(segment ? { reasoning: segment } : {}),
      };
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
            duration_s: Math.max(0, endTs - (nextTools[i].at ?? endTs)),
          };
          break;
        }
      }
    } else if (kind === "assistant_delta") {
      assistant += f.text ?? "";
    } else if (kind === "reasoning_delta") {
      reasoning += f.text ?? "";
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
  return { tools: nextTools, assistant, reasoning, error: errorText, sawDone, finalSessionId, ctxTokens };
}
