export function isGone(error) {
  const text = String(error?.message ?? error ?? "").toLowerCase();
  return /-32004\b/.test(text) || (/\bnot[-_ ]found\b/.test(text) && !/method[-_ ]not[-_ ]found/.test(text));
}
