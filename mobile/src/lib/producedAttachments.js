export function compactProducedTool(t, produced) {
  if (!produced?.length) return t;
  const text = t.output || t.result || '';
  const hit = produced.find((a) => a?.path && text.includes(a.path));
  if (!hit) return t;
  const label = `Generated · ${hit.name}`;
  return { ...t, output: label, result: label };
}
