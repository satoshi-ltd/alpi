// Mirrors alpi/outputs.py derive_summary; notificationSummary.fixtures.mjs holds the corpus both test against.
export const SUMMARY_MAX = 200;
export const LABEL_MAX_CHARS = 32;
export const LABEL_MAX_WORDS = 5;
const SUMMARY_FLOOR = 60;
const OPEN_ENDS = [":", "："];

const ALLOWED_EMOJI = new Set([0x1f534, 0x1f7e1, 0x1f7e2]);
const EMOJI_RANGES = [[0x1f300, 0x1faff], [0x1f1e6, 0x1f1ff], [0x2600, 0x27bf], [0x2b00, 0x2bff], [0xfe00, 0xfe0f]];
const EMOJI_SINGLES = new Set([0x200d, 0x20e3]);

const HTML = /<\/?[A-Za-z][^>]*>/g;
const LINK = /!?\[([^\]]*)\]\([^)]*\)/g;
const CODE_SPAN = /`[^`]*`/g;
const URL = /https?:\/\/[^\s<>]*[^\s<>*_~.,;:!?'")\]]/g;
const SLOT = /\u0000([0-9]+)\u0000/g;
const STRONG = /\*\*(.+?)\*\*/g;
const EM_STAR = /(^|[^A-Za-z0-9_*])\*([^\s*](?:[^*]*[^\s*])?)\*(?![A-Za-z0-9_*])/g;
const EM_UNDERSCORE = /(^|[^A-Za-z0-9_])_([^\s_](?:[^_]*[^\s_])?)_(?![A-Za-z0-9_])/g;
const STRIKE = /~~(.+?)~~/g;
const LINE_BREAK = /\r\n?|[\u2028\u2029\u0085]/g;
const SEPARATOR_CHAR = /[\u001c-\u001f]/g;

const HR = /^\s*([-*_])\1{2,}\s*$/;
const HEADING = /^\s*(#{1,6})\s+(.*?)\s*$/;
const QUOTE = /^\s*>\s?(.*)$/;
const LIST = /^\s*([-*•]|[0-9]+[.)])\s+(.*)$/;
const LABEL_ONLY = /^\*\*\s*([^*]+?)\s*\*\*\s*:?$/;
const LABEL_LINE = /^\*\*[^*]+\*\*:?\s+\S/;
const STATUS_LINE = /^[\u{1F534}\u{1F7E1}\u{1F7E2}]\s+\S/u;
const SEPARATOR_CELL = /^:?-+:?$/;

const codePoints = (text) => Array.from(text);
const endsOpen = (text) => OPEN_ENDS.some((end) => text.endsWith(end));

export function canonicalText(text) {
  return String(text ?? "").replace(LINE_BREAK, "\n").replace(SEPARATOR_CHAR, " ").replace(/\uFEFF/g, "");
}

function isDisallowedEmoji(cp) {
  if (ALLOWED_EMOJI.has(cp)) return false;
  if (EMOJI_SINGLES.has(cp)) return true;
  return EMOJI_RANGES.some(([lo, hi]) => cp >= lo && cp <= hi);
}

export function sanitizeEmoji(text) {
  if (!text) return "";
  const kept = codePoints(String(text)).filter((ch) => !isDisallowedEmoji(ch.codePointAt(0))).join("");
  return kept.replace(/[^\S\n]{2,}/g, " ").replace(/[^\S\n]+(?=\n)/g, "").trim();
}

export function plainInline(text) {
  const held = [];
  const hold = (token) => {
    held.push(token.startsWith("`") ? token.slice(1, -1) : token);
    return `\u0000${held.length - 1}\u0000`;
  };
  return String(text ?? "")
    .replace(/\u0000/g, "")
    .replace(CODE_SPAN, hold)
    .replace(HTML, "")
    .replace(LINK, "$1")
    .replace(URL, hold)
    .replace(STRONG, "$1")
    .replace(EM_STAR, "$1$2")
    .replace(EM_UNDERSCORE, "$1$2")
    .replace(STRIKE, "$1")
    .replace(SLOT, (_, i) => held[Number(i)]);
}

export function notificationTitle(text) {
  if (!text || typeof text !== "string") return "";
  return sanitizeEmoji(canonicalText(text)).replace(/\s+/g, " ").trim();
}

// For agent.message frames without a summary key: those daemons predate 0.17.17 and send titles with their markdown.
export function legacyTitle(text) {
  if (!text || typeof text !== "string") return "";
  const canonical = canonicalText(text);
  const heading = canonical.match(HEADING);
  return sanitizeEmoji(plainInline(heading ? heading[2] : canonical)).replace(/\s+/g, " ").trim();
}

function isLabel(line) {
  const m = line.match(LABEL_ONLY);
  if (!m) return false;
  const label = m[1].replace(/:+$/, "").trim();
  return codePoints(label).length <= LABEL_MAX_CHARS && label.split(/\s+/).filter(Boolean).length <= LABEL_MAX_WORDS;
}

function isTableSeparator(line) {
  if (!line.includes("|")) return false;
  let s = line.trim();
  if (s.startsWith("|")) s = s.slice(1);
  if (s.endsWith("|")) s = s.slice(0, -1);
  return s.split("|").every((cell) => SEPARATOR_CELL.test(cell.trim()));
}

const fenceOf = (line) => (line.startsWith("```") || line.startsWith("~~~") ? line.slice(0, 3) : "");

function* proseUnits(body) {
  const lines = body.split("\n");
  let para = [];
  let fence = "";
  let table = false;
  for (let i = 0; i < lines.length; i += 1) {
    const line = sanitizeEmoji(lines[i]);
    const marker = fenceOf(line);
    if (fence) {
      if (marker === fence) fence = "";
      continue;
    }
    if (table && line && line.includes("|")) continue;
    table = false;
    if (marker || !line || HR.test(line) || HEADING.test(line) || isLabel(line)) {
      fence = marker;
    } else if (line.includes("|") && i + 1 < lines.length && isTableSeparator(lines[i + 1])) {
      table = true;
    } else if (!line.startsWith("|")) {
      const quote = line.match(QUOTE);
      const content = quote ? quote[1].trim() : line;
      const item = content.match(LIST);
      if (!(item || LABEL_LINE.test(content) || STATUS_LINE.test(content))) {
        const text = plainInline(content).trim();
        if (text) para.push(text);
        continue;
      }
      if (para.length) {
        yield para.join(" ");
        para = [];
      }
      const text = plainInline(item ? item[2] : content).trim();
      if (text) yield text;
      continue;
    }
    if (para.length) {
      yield para.join(" ");
      para = [];
    }
  }
  if (para.length) yield para.join(" ");
}

function clipSummary(input) {
  let text = input.replace(/\s+/g, " ").trim();
  const chars = codePoints(text);
  if (chars.length > SUMMARY_MAX) {
    const head = chars.slice(0, SUMMARY_MAX + 1).join("");
    let best = -1;
    for (const m of head.matchAll(/[.!?](?=\s)/g)) {
      const end = codePoints(head.slice(0, m.index + 1)).length;
      if (end >= SUMMARY_FLOOR && end <= SUMMARY_MAX) best = end;
    }
    if (best !== -1) {
      text = chars.slice(0, best).join("");
    } else {
      const cut = chars.slice(0, SUMMARY_MAX - 1).join("");
      const space = cut.lastIndexOf(" ");
      const spaceAt = space === -1 ? -1 : codePoints(cut.slice(0, space)).length;
      text = `${(spaceAt >= SUMMARY_FLOOR ? cut.slice(0, space) : cut).replace(/[ ,;:：]+$/, "")}…`;
    }
  }
  if (endsOpen(text)) text = `${codePoints(text).slice(0, -1).join("").trimEnd()}…`;
  return text;
}

export function deriveSummary(body) {
  let text = "";
  for (const unit of proseUnits(canonicalText(typeof body === "string" ? body : ""))) {
    text = text ? `${text} ${unit}` : unit;
    if (!endsOpen(text) || codePoints(text).length >= SUMMARY_MAX) break;
  }
  return text ? clipSummary(text) : "";
}
