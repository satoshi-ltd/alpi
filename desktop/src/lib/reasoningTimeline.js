function trailingAfter(segments, turnReasoning) {
  let rest = String(turnReasoning ?? "").trim();
  for (const seg of segments) {
    const trimmed = rest.replace(/^\s+/, "");
    if (!trimmed.startsWith(seg)) break;
    rest = trimmed.slice(seg.length);
  }
  return rest.trim();
}

export function reasoningTimeline(tools, turnReasoning) {
  const list = (Array.isArray(tools) ? tools : []).filter((t) => t?.name !== "ask_user");
  const perTool = list.map((t) => String(t.reasoning ?? "").trim());
  const trailing = trailingAfter(perTool.filter(Boolean), turnReasoning);
  const items = [];
  list.forEach((t, i) => {
    if (perTool[i]) items.push({ kind: "text", text: perTool[i] });
    const last = items[items.length - 1];
    if (last?.kind === "tools") last.names.push(t.name);
    else items.push({ kind: "tools", names: [t.name] });
  });
  if (trailing) items.push({ kind: "text", text: trailing });
  while (items.length && items[items.length - 1].kind === "tools") items.pop();
  return items;
}

export function lastLine(text) {
  const lines = String(text || "").split("\n").map((s) => s.trim()).filter(Boolean);
  return lines[lines.length - 1] ?? "";
}
