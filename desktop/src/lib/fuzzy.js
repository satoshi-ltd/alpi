export function fuzzyMatch(text, query) {
  const hay = String(text ?? "");
  const q = String(query ?? "").trim().toLowerCase();
  if (!q) return { score: 0, ranges: [] };
  const lower = hay.toLowerCase();
  const at = lower.indexOf(q);
  if (at >= 0) {
    const wordStart = at === 0 || /[\s\-_/@#·.]/.test(lower[at - 1]);
    return { score: 1000 - at + (wordStart ? 200 : 0), ranges: [[at, at + q.length]] };
  }
  const ranges = [];
  let from = 0;
  let gaps = 0;
  for (const ch of q) {
    if (ch === " ") continue;
    const idx = lower.indexOf(ch, from);
    if (idx < 0) return null;
    const last = ranges[ranges.length - 1];
    if (last && last[1] === idx) last[1] = idx + 1;
    else {
      if (last) gaps += idx - last[1];
      ranges.push([idx, idx + 1]);
    }
    from = idx + 1;
  }
  return { score: 500 - gaps - ranges.length * 10 - ranges[0][0], ranges };
}

export function splitByRanges(text, ranges = []) {
  const s = String(text ?? "");
  if (!ranges.length) return [{ text: s, hit: false }];
  const out = [];
  let pos = 0;
  for (const [a, b] of ranges) {
    if (a > pos) out.push({ text: s.slice(pos, a), hit: false });
    out.push({ text: s.slice(a, b), hit: true });
    pos = b;
  }
  if (pos < s.length) out.push({ text: s.slice(pos), hit: false });
  return out;
}
