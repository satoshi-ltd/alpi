export function stripProducedImageMarkdown(text, produced) {
  if (!produced?.length || !text) return text;
  let out = text;
  for (const a of produced) {
    if (!a?.path) continue;
    const esc = a.path.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    if (a.kind === "image") {
      out = out.replace(new RegExp(`!\\[[^\\]]*\\]\\(\\s*${esc}(?:\\s+"[^"]*")?\\s*\\)`, "g"), "");
    }
    out = out.replace(new RegExp(`^\\s*Path:\\s*\`?${esc}\`?\\s*$`, "gim"), "");
    out = out.replace(new RegExp(`^\\s*\`?${esc}\`?\\s*$`, "gm"), "");
  }
  return out.replace(/\n{3,}/g, "\n\n").trim();
}

export function assistantWithProducedImages(text, produced) {
  const stripped = stripProducedImageMarkdown(text, produced);
  const imgs = (produced || [])
    .filter((a) => a?.kind === "image" && a?.path)
    .map((a) => `![](${a.path})`)
    .join("\n\n");
  return [stripped, imgs].filter(Boolean).join("\n\n");
}

export function nonImageProduced(produced) {
  return (produced || []).filter((a) => a?.kind !== "image");
}

export function compactProducedTool(t, produced) {
  if (!produced?.length) return t;
  const text = t.output || t.result || "";
  const hit = produced.find((a) => a?.path && text.includes(a.path));
  if (!hit) return t;
  const label = `Generated · ${hit.name}`;
  return { ...t, output: label, result: label };
}
