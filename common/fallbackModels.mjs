export const FALLBACK_KEY = "fallback_models";
export const MAX_FALLBACKS = 16;
export const FALLBACK_HINT = "Tried in order when the main model's provider fails.";

export function hasFallbackModels(detail) {
  return !!detail && Array.isArray(detail[FALLBACK_KEY]);
}

export function fallbackList(detail) {
  if (!hasFallbackModels(detail)) return [];
  return detail[FALLBACK_KEY].filter((m) => typeof m === "string" && m && m !== detail.model);
}

export function addFallback(list, model, main) {
  if (!model || model === main || list.includes(model) || list.length >= MAX_FALLBACKS) return list;
  return [...list, model];
}

export function removeFallback(list, index) {
  return list.filter((_, i) => i !== index);
}

export function moveFallback(list, index, delta) {
  const to = index + delta;
  if (index < 0 || index >= list.length || to < 0 || to >= list.length) return list;
  const next = [...list];
  [next[index], next[to]] = [next[to], next[index]];
  return next;
}

export function fallbackCandidates(models, list, main) {
  return (models ?? []).filter((m) => m && m !== main && !list.includes(m));
}
