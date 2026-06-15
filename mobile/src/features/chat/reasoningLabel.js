export function fmtDuration(s) {
  const n = Math.round(s || 0);
  if (n < 60) return `${n}s`;
  const m = Math.floor(n / 60);
  const r = n % 60;
  return r ? `${m}m ${r}s` : `${m}m`;
}

// "Thought for Ns" only with a real duration; bare "Thought" when reasoned_s is missing/0 (old sessions) so it never reads "Thought for 0s".
export function thoughtLabel(seconds) {
  return seconds >= 1 ? `Thought for ${fmtDuration(seconds)}` : 'Thought';
}
