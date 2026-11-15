export function sizeLabel(n) {
  const b = Math.max(0, Number(n) || 0);
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(1)} MB`;
}

const ABBREVIATION = /\b(?:e\.g|i\.e|etc|vs|cf|approx)\.$/i;

export function firstSentence(text) {
  const flat = String(text || "")
    .replace(/^[ \t]*(?:#{1,6}|>)[ \t>]*/gm, "")
    .replace(/`/g, "")
    .replace(/(^|[^\w])(\*\*|__)(\S(?:.*?\S)?)\2(?!\w)/g, "$1$3")
    .replace(/(^|[^\w*])([*_])(\S(?:.*?\S)?)\2(?![\w*])/g, "$1$3")
    .replace(/\*/g, "")
    .replace(/\s+/g, " ")
    .trim();
  if (!flat) return "";
  const end = /[.!?](?=\s|$)/g;
  for (let m = end.exec(flat); m; m = end.exec(flat)) {
    const head = flat.slice(0, m.index + 1);
    if (!ABBREVIATION.test(head)) return head;
  }
  return flat;
}

export function memoryShare(used, limit) {
  if (used == null || !limit) return null;
  return Math.round((Number(used) / Number(limit)) * 100);
}

export function memoryMeta(used, limit, flagWord = null) {
  if (flagWord) return { meta: flagWord, tone: "danger" };
  const pct = memoryShare(used, limit);
  return pct == null ? { meta: "", tone: null } : { meta: `${pct}%`, tone: null };
}

export function skillMeta(skill, flagWord = null) {
  if (flagWord) return { meta: flagWord, tone: "danger" };
  if (skill.status && skill.status !== "active") return { meta: skill.status, tone: skill.status === "invalid" ? "danger" : null };
  return { meta: sizeLabel(skill.size), tone: null };
}

export function factLabel(label) {
  const s = String(label || "");
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}
