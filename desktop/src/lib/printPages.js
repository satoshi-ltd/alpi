import { exportArticle, exportStamp, exportTitle } from "../../../common/messageExport.mjs";
import { fontStacks, palettes } from "../../../common/tokens.mjs";

const P = palettes.light;

// The paper is picked in the print sheet after pagination, so pages fit the smaller of A4 and Letter inside the 16 mm margins.
export const PAGE_WIDTH = 672;
export const PAGE_HEIGHT = 928;
export const HEAD_HEIGHT = 32;
export const FOOT_HEIGHT = 28;
export const BODY_HEIGHT = PAGE_HEIGHT - HEAD_HEIGHT - FOOT_HEIGHT;
export const PAGE_SLACK = 8;

export const PAGE_CSS = `
@media print { @page { size: portrait; } }
.alpi-export .pp-page { box-sizing: border-box; width: ${PAGE_WIDTH}px; height: ${PAGE_HEIGHT}px; overflow: hidden; display: flex; flex-direction: column;
  break-inside: avoid; page-break-inside: avoid; break-after: page; page-break-after: always; }
.alpi-export .pp-page:last-child { break-after: auto; page-break-after: auto; }
.alpi-export .pp-head, .alpi-export .pp-foot { flex: none; box-sizing: border-box; display: flex; align-items: center; gap: 6px; overflow: hidden; white-space: nowrap;
  font-family: ${fontStacks.mono}; font-size: 7.5pt; color: ${P.ink3}; }
.alpi-export .pp-head { height: ${HEAD_HEIGHT}px; padding-bottom: 6px; margin: 0; border-bottom: .5px solid ${P.line2}; }
.alpi-export .pp-head b { font-family: ${fontStacks.sans}; color: ${P.ink}; font-size: 8.5pt; }
.alpi-export .pp-foot { height: ${FOOT_HEIGHT}px; padding-top: 6px; border-top: .5px solid ${P.line2}; }
.alpi-export .pp-gap { flex: 1; }
.alpi-export .pp-title { overflow: hidden; text-overflow: ellipsis; min-width: 0; }
.alpi-export, .alpi-export th, .alpi-export td { overflow-wrap: anywhere; }
.alpi-export .pp-body { flex: none; height: ${BODY_HEIGHT}px; overflow: hidden; }
.alpi-export .pp-unit { display: flow-root; }
.alpi-export .pp-scaled { transform-origin: top left; }
.alpi-export .pp-line { display: block; overflow-wrap: anywhere; }`;

const TEXT_TAGS = new Set(["P", "BLOCKQUOTE", "H1"]);
const WORDS = /\S+\s*|\s+/g;
const SEGMENTER = typeof Intl !== "undefined" && Intl.Segmenter ? new Intl.Segmenter(undefined, { granularity: "word" }) : null;

export function splitWords(text, segmenter = SEGMENTER) {
  if (!segmenter) return text.match(WORDS) || [];
  const words = [];
  for (const { segment } of segmenter.segment(text)) {
    if (words.length && !segment.trim()) words[words.length - 1] += segment;
    else words.push(segment);
  }
  return words;
}

export function paginate(blocks, pageHeight) {
  const pages = [];
  let page = [];
  let used = 0;
  let held = false;
  const flush = () => {
    if (page.length) pages.push(page);
    page = [];
    used = 0;
    held = false;
  };
  const fits = (h) => used + h <= pageHeight;
  const splittable = (b) => b?.parts?.length > 1;
  const lead = (i) => {
    const b = blocks[i];
    if (!b) return 0;
    if (splittable(b)) return b.keep && b.height <= pageHeight ? b.height : b.chrome + b.parts[0];
    if (b.height > pageHeight) return 0;
    return b.keepWithNext ? b.height + lead(i + 1) : b.height;
  };
  blocks.forEach((b, i) => {
    if (!splittable(b)) {
      if (!fits(b.height > pageHeight ? b.height : lead(i)) && page.length && !(held && fits(b.height))) flush();
      if (b.height > pageHeight) {
        page.push({ block: i, scale: pageHeight / b.height });
        flush();
        return;
      }
      page.push({ block: i });
      used += b.height;
      held = Boolean(b.keepWithNext);
      return;
    }
    if (!fits(b.height) && page.length && !held && b.keep && b.height <= pageHeight) flush();
    held = false;
    if (fits(b.height)) {
      page.push({ block: i, from: 0, to: b.parts.length });
      used += b.height;
      return;
    }
    let k = 0;
    while (k < b.parts.length) {
      let take = 0;
      let h = b.chrome;
      while (k + take < b.parts.length && fits(h + b.parts[k + take])) h += b.parts[k + take++];
      if (!take && page.length) {
        flush();
        continue;
      }
      if (!take) {
        page.push({ block: i, from: k, to: k + 1, scale: pageHeight / (b.chrome + b.parts[k]) });
        flush();
        k += 1;
        continue;
      }
      page.push({ block: i, from: k, to: k + take });
      used += h;
      k += take;
      if (k < b.parts.length) flush();
    }
  });
  flush();
  return pages.length ? pages : [[]];
}

function splitKind(el) {
  if (el.tagName === "UL" || el.tagName === "OL") return "list";
  if (el.tagName === "TABLE" && el.tBodies.length) return "table";
  if (el.tagName === "PRE") return "code";
  if (TEXT_TAGS.has(el.tagName)) return "text";
  return null;
}

function textTokens(el) {
  const tokens = [];
  for (const child of el.childNodes) {
    if (child.nodeType === 3) for (const text of splitWords(child.data)) tokens.push({ text });
    else if (child.nodeType === 1 && !child.children.length) for (const text of splitWords(child.textContent)) tokens.push({ text, tag: child });
    else if (child.nodeType === 1) tokens.push({ node: child });
  }
  return tokens;
}

export function articleUnits(article) {
  const units = [];
  for (const cell of article.querySelectorAll(".ax-sheet > tbody > tr > td")) {
    for (const el of [...cell.children]) {
      if (el.matches(".ax-head, .ax-foot")) continue;
      const split = splitKind(el);
      units.push({
        node: el,
        split,
        lines: split === "code" ? el.textContent.replace(/\n$/, "").split("\n") : null,
        tokens: split === "text" ? textTokens(el) : null,
        keepWithNext: el.tagName === "H2" || el.tagName === "H3",
      });
    }
  }
  return units;
}

function word(token) {
  const span = document.createElement("span");
  span.className = "pp-word";
  if (token.node) span.append(token.node.cloneNode(true));
  else if (token.tag) {
    const inner = token.tag.cloneNode(false);
    inner.textContent = token.text;
    span.append(inner);
  } else span.textContent = token.text;
  return span;
}

function piece(unit, from, to) {
  const { node, split } = unit;
  if (!split || from === undefined) return node.cloneNode(true);
  const shell = node.cloneNode(false);
  if (split === "list") {
    for (const li of [...node.children].slice(from, to)) shell.append(li.cloneNode(true));
  } else if (split === "table") {
    if (unit.cols) {
      shell.style.tableLayout = "fixed";
      const group = document.createElement("colgroup");
      for (const width of unit.cols) {
        const col = document.createElement("col");
        col.style.width = `${width}px`;
        group.append(col);
      }
      shell.append(group);
    }
    if (node.tHead) shell.append(node.tHead.cloneNode(true));
    const body = node.tBodies[0].cloneNode(false);
    for (const tr of [...node.tBodies[0].rows].slice(from, to)) body.append(tr.cloneNode(true));
    shell.append(body);
  } else if (split === "code") {
    const code = document.createElement("code");
    for (const text of unit.lines.slice(from, to)) {
      const line = document.createElement("span");
      line.className = "pp-line";
      line.textContent = text || " ";
      code.append(line);
    }
    shell.append(code);
  } else {
    const start = unit.breaks ? unit.breaks[from] : 0;
    const end = unit.breaks && to < unit.breaks.length ? unit.breaks[to] : unit.tokens.length;
    for (const token of unit.tokens.slice(start, end)) shell.append(word(token));
  }
  return shell;
}

function wrap(child, scale) {
  const unit = document.createElement("div");
  unit.className = scale ? "pp-unit pp-scaled" : "pp-unit";
  if (scale) unit.style.transform = `scale(${scale})`;
  unit.append(child);
  return unit;
}

const boxOf = (el) => el.getBoundingClientRect();

function lineStarts(rects) {
  const starts = [];
  const tops = [];
  let bottom = -Infinity;
  rects.forEach((r, k) => {
    if (r.top >= bottom - 0.5) {
      starts.push(k);
      tops.push(r.top);
      bottom = r.top + r.height;
    } else bottom = Math.max(bottom, r.top + r.height);
  });
  return { starts, tops, lastBottom: bottom };
}

function measureParts(u, wrapper, rectOf) {
  if (u.split === "text") {
    const { starts, tops, lastBottom } = lineStarts([...wrapper.querySelectorAll(".pp-word")].map(rectOf));
    if (starts.length < 2) return null;
    u.breaks = starts;
    return tops.map((t, k) => (k + 1 < tops.length ? tops[k + 1] - t : lastBottom - t));
  }
  const els = u.split === "list" ? [...wrapper.firstElementChild.children]
    : u.split === "table" ? [...wrapper.querySelectorAll("tbody > tr")]
      : [...wrapper.querySelectorAll(".pp-line")];
  if (els.length < 2) return null;
  if (u.split === "table") {
    const cells = [...(wrapper.querySelector("thead tr") || els[0]).cells];
    const cols = cells.map((c) => rectOf(c).width);
    if (cols.length && cols.every((w) => Number.isFinite(w) && w > 0)) u.cols = cols;
  }
  const rects = els.map(rectOf);
  return rects.map((r, k) => (k + 1 < rects.length ? rects[k + 1].top - r.top : r.height));
}

export function measureBlocks(units, host, rectOf = boxOf) {
  const wrappers = units.map((u) => host.appendChild(wrap(u.split ? piece(u, 0, Infinity) : piece(u))));
  return units.map((u, i) => {
    const height = rectOf(wrappers[i]).height;
    const block = { height, keepWithNext: u.keepWithNext };
    const parts = u.split ? measureParts(u, wrappers[i], rectOf) : null;
    if (!parts) return block;
    const sum = parts.reduce((a, b) => a + b, 0);
    return { ...block, parts, chrome: Math.max(0, height - sum), keep: u.split === "code" || u.split === "text" };
  });
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function runningHeader(message, mark) {
  const head = el("header", "pp-head");
  if (mark) head.append(mark.cloneNode(true));
  head.append(el("b", "", "alpi"));
  const who = [message?.profile ? `@${message.profile}` : "", message?.server || ""].filter(Boolean).join(" · ");
  if (who) head.append(el("span", "pp-who", `· ${who}`));
  head.append(el("span", "pp-gap"), el("span", "pp-title", exportTitle(message)));
  return head;
}

function runningFooter(message, n, total) {
  const foot = el("footer", "pp-foot");
  const left = [message?.profile ? `@${message.profile}` : "", exportStamp(message?.at)].filter(Boolean).join(" · ");
  foot.append(el("span", "pp-sign", left), el("span", "pp-gap"), el("span", "pp-number", `${n} / ${total}`));
  return foot;
}

export function renderPrintPages(message, measureHost, rectOf = boxOf) {
  const template = document.createElement("template");
  template.innerHTML = exportArticle(message);
  const article = template.content.firstElementChild;
  const mark = article.querySelector(".ax-foot svg");
  const units = articleUnits(article);
  const pages = paginate(measureBlocks(units, measureHost, rectOf), BODY_HEIGHT - PAGE_SLACK);
  const shell = article.cloneNode(false);
  pages.forEach((items, n) => {
    const page = el("section", "pp-page");
    const body = el("div", "pp-body");
    for (const { block, from, to, scale } of items) body.append(wrap(piece(units[block], from, to), scale));
    page.append(runningHeader(message, mark), body, runningFooter(message, n + 1, pages.length));
    shell.append(page);
  });
  return shell;
}
