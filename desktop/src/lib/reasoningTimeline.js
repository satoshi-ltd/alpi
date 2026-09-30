function trailingAfter(segments, turnReasoning) {
  let rest = String(turnReasoning ?? "").trim();
  for (const seg of segments) {
    const trimmed = rest.replace(/^\s+/, "");
    if (!trimmed.startsWith(seg)) break;
    rest = trimmed.slice(seg.length);
  }
  return rest.trim();
}

function finite(v) {
  return typeof v === "number" && Number.isFinite(v) ? v : undefined;
}

function storedSpans(spans, count) {
  if (!Array.isArray(spans) || !spans.length) return null;
  const at = new Map();
  for (const span of spans) {
    const idx = Number.isInteger(span?.before_tool) ? Math.min(Math.max(span.before_tool, 0), count) : null;
    const secs = finite(span?.seconds);
    if (idx === null || secs === undefined) continue;
    const slot = at.get(idx) ?? { seconds: 0, texts: [] };
    slot.seconds += secs;
    const text = typeof span.text === "string" ? span.text.trim() : "";
    if (text) slot.texts.push(text);
    at.set(idx, slot);
  }
  return at.size ? at : null;
}

function mergedTimeline(all, perTool, trailing) {
  const items = [];
  all.forEach((t, i) => {
    if (perTool[i]) items.push({ kind: "text", text: perTool[i] });
    if (t?.name === "ask_user") return;
    const last = items[items.length - 1];
    if (last?.kind === "tools") last.names.push(t.name);
    else items.push({ kind: "tools", names: [t.name] });
  });
  if (trailing) items.push({ kind: "text", text: trailing });
  while (items.length && items[items.length - 1].kind === "tools") items.pop();
  return items;
}

export function processTimeline(tools, turnReasoning, totalSeconds, reasoningSpans, { mergeUnattributed = false } = {}) {
  const all = Array.isArray(tools) ? tools : [];
  const stored = storedSpans(reasoningSpans, all.length);
  const withText = stored && [...stored.values()].some((slot) => slot.texts.length);
  const perTool = all.map((t) => String(t?.reasoning ?? "").trim());
  const trailing = trailingAfter(perTool.filter(Boolean), turnReasoning);
  const textAt = (i) => {
    const slot = stored?.get(i);
    if (withText) {
      const own = slot?.texts.join("\n\n") ?? "";
      const prose = i < all.length ? perTool[i] : "";
      return prose && !own.includes(prose) ? [own, prose].filter(Boolean).join("\n\n") : own;
    }
    return i < all.length ? perTool[i] : trailing;
  };
  const secondsAt = (i) => (stored ? stored.get(i)?.seconds : i < all.length ? finite(all[i]?.reasoned_s) : undefined);
  const entries = [];
  let ordinal = 0;
  const pushSpan = (i, extra = {}) => {
    const text = textAt(i);
    const seconds = secondsAt(i);
    if (text || (stored?.has(i) && seconds >= 1)) entries.push({ kind: "reasoning", key: `r${ordinal++}`, text, seconds, ...extra });
  };
  all.forEach((t, i) => {
    const id = t?.tool_id ?? `${t?.name}:${i}`;
    pushSpan(i);
    if (t?.name !== "ask_user") entries.push({ kind: "tool", key: `t:${id}`, tool: t });
  });
  pushSpan(all.length, { tail: true });
  if (stored) return entries;
  const spans = entries.filter((e) => e.kind === "reasoning");
  const total = finite(totalSeconds);
  const known = spans.filter((e) => e.seconds !== undefined);
  if (mergeUnattributed && !known.length && spans.length > 1) {
    const text = spans.map((e) => e.text).join("\n\n");
    const timeline = mergedTimeline(all, perTool, trailing);
    return [
      { kind: "reasoning", key: "r0", text, seconds: total, timeline },
      ...entries.filter((e) => e.kind === "tool"),
    ];
  }
  if (total !== undefined && !known.length && spans.length === 1) spans[0].seconds = total;
  const tail = spans.find((e) => e.tail);
  if (total !== undefined && known.length && tail && tail.seconds === undefined) {
    tail.seconds = Math.max(0, total - known.reduce((sum, e) => sum + e.seconds, 0));
  }
  return entries;
}

export function lastLine(text) {
  const lines = String(text || "").split("\n").map((s) => s.trim()).filter(Boolean);
  return lines[lines.length - 1] ?? "";
}
