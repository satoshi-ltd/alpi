export const LABEL_MAX_CHARS = 32;
export const LABEL_MAX_WORDS = 5;

const FENCE = /^\s*```/;
const HR = /^\s*([-*_])\1{2,}\s*$/;
const HEADING = /^\s*(#{1,6})\s+(.+?)\s*$/;
const QUOTE = /^\s*>\s?(.*)$/;
const PLAIN_BULLET = /^\s*[-•*]\s+(.*)$/;
const EMOJI_BULLET = /^\s*(\p{Extended_Pictographic}(?:️|‍\p{Extended_Pictographic})*)\s+(\S.*)$/u;
const ORDERED = /^\s*(\d+)[.)]\s+(.*)$/;
const STANDALONE_LABEL = /^\*\*\s*([^*]+?)\s*\*\*$/;
const INLINE_LABEL_COLON_IN = /^\*\*\s*([^*]+?)\s*:\s*\*\*\s+(\S.*)$/;
const INLINE_LABEL_COLON_OUT = /^\*\*\s*([^*]+?)\s*\*\*\s*:\s+(\S.*)$/;
const INLINE_MD = /(`([^`]+?)`|\*\*([^*]+?)\*\*|\*([^*]+?)\*)/g;
const SEP_CELL = /^:?-+:?$/;

const wordCount = (s) => s.trim().split(/\s+/).filter(Boolean).length;

const isListLine = (s) => PLAIN_BULLET.test(s) || EMOJI_BULLET.test(s) || ORDERED.test(s);

export function splitRow(line) {
  return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim());
}

function isSeparatorRow(line) {
  if (!line.includes('|')) return false;
  const cells = splitRow(line);
  return cells.length > 0 && cells.every((c) => SEP_CELL.test(c));
}

function labelBody(line) {
  const m = line.match(INLINE_LABEL_COLON_IN) || line.match(INLINE_LABEL_COLON_OUT);
  if (!m) return null;
  const label = m[1].trim();
  if (label.length > LABEL_MAX_CHARS || wordCount(label) > LABEL_MAX_WORDS) return null;
  return { kind: 'labelBody', label, body: m[2] };
}

function listItem(line, ordered) {
  if (ordered) {
    const m = line.match(ORDERED);
    return { marker: `${m[1]}.`, text: m[2].trim() };
  }
  const p = line.match(PLAIN_BULLET);
  if (p) return { marker: '•', text: p[1].trim() };
  const e = line.match(EMOJI_BULLET);
  return { marker: e[1], text: e[2].trim() };
}

export function parseNotificationBody(body) {
  const lines = String(body ?? '').split('\n');
  const blocks = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i].replace(/\s+$/, '');

    if (FENCE.test(line)) {
      const buf = [];
      i += 1;
      while (i < lines.length && !FENCE.test(lines[i])) { buf.push(lines[i]); i += 1; }
      i += 1;
      blocks.push({ kind: 'code', text: buf.join('\n') });
      continue;
    }
    if (!line.trim() || HR.test(line)) { i += 1; continue; }

    let m = line.match(HEADING);
    if (m) {
      if (m[1].length <= 2) blocks.push({ kind: 'heading', text: m[2] });
      else blocks.push({ kind: 'label', label: m[2].replace(/:\s*$/, '') });
      i += 1;
      continue;
    }

    if (QUOTE.test(line) && !isListLine(line)) {
      const buf = [];
      while (i < lines.length && QUOTE.test(lines[i]) && !isListLine(lines[i])) {
        buf.push(lines[i].match(QUOTE)[1].trim());
        i += 1;
      }
      blocks.push({ kind: 'quote', text: buf.join(' ').trim() });
      continue;
    }

    if (isListLine(line)) {
      const ordered = ORDERED.test(line);
      const items = [];
      while (i < lines.length) {
        const cur = lines[i].replace(/\s+$/, '');
        if (!isListLine(cur) || ORDERED.test(cur) !== ordered) break;
        items.push(listItem(cur, ordered));
        i += 1;
      }
      blocks.push({ kind: 'list', ordered, items });
      continue;
    }

    if (line.includes('|') && i + 1 < lines.length && isSeparatorRow(lines[i + 1].replace(/\s+$/, ''))) {
      const headers = splitRow(line);
      i += 2;
      const rows = [];
      while (i < lines.length) {
        const r = lines[i].replace(/\s+$/, '');
        if (!r.trim() || !r.includes('|') || isSeparatorRow(r)) break;
        rows.push(splitRow(r));
        i += 1;
      }
      blocks.push({ kind: 'table', headers, rows });
      continue;
    }

    m = line.match(STANDALONE_LABEL);
    if (m) { blocks.push({ kind: 'label', label: m[1].replace(/:\s*$/, '') }); i += 1; continue; }

    const lb = labelBody(line.trim());
    if (lb) { blocks.push(lb); i += 1; continue; }

    blocks.push({ kind: 'p', text: line.trim() });
    i += 1;
  }
  return blocks;
}

export function inlineSegments(text) {
  const segs = [];
  let last = 0;
  let m;
  INLINE_MD.lastIndex = 0;
  while ((m = INLINE_MD.exec(text)) !== null) {
    if (m.index > last) segs.push({ t: 'text', v: text.slice(last, m.index) });
    if (m[2] != null) segs.push({ t: 'code', v: m[2] });
    else if (m[3] != null) segs.push({ t: 'bold', v: m[3] });
    else segs.push({ t: 'italic', v: m[4] });
    last = INLINE_MD.lastIndex;
  }
  if (last < text.length) segs.push({ t: 'text', v: text.slice(last) });
  return segs;
}
