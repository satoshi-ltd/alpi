export function mergeProfileDraft({
  draft,
  baseline,
  prevBaseline,
  profileKey,
  prevProfileKey,
}) {
  if (profileKey !== prevProfileKey) {
    return { ...baseline };
  }
  const next = { ...draft };
  for (const key of Object.keys(baseline)) {
    if (draft[key] === prevBaseline[key]) {
      next[key] = baseline[key];
    }
  }
  return next;
}
