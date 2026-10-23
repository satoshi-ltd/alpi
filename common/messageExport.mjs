import { chartSvg } from "./chartSpec.mjs";
import { ALPACA_LOW_FOLD, foldPolygons } from "./folds.mjs";
import { inlineSegments, parseNotificationBody } from "./notificationBody.mjs";
import { fontStacks, palettes } from "./tokens.mjs";

const P = palettes.light;
const STAMP = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

const escapeHtml = (text) => String(text ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

export function exportStamp(unixSeconds) {
  return unixSeconds ? STAMP.format(new Date(unixSeconds * 1000)) : "";
}

export function exportSlug(text) {
  return String(text || "")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

export function exportTitle(message) {
  return String(message?.title || "").replace(/\s+/g, " ").trim();
}

export function exportFileName(message, ext) {
  const d = message?.at ? new Date(message.at * 1000) : null;
  const day = d ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}` : "";
  const base = exportSlug(exportTitle(message)) || exportSlug([message?.profile, day].filter(Boolean).join(" ")) || "message";
  return `${base}.${ext}`;
}

export function exportMeta(message) {
  return [message?.profile ? `@${message.profile}` : "", message?.server || "", exportStamp(message?.at)].filter(Boolean).join(" · ");
}

export function exportFooter(message) {
  const who = message?.profile ? `@${message.profile}${message.server ? ` on ${message.server}` : ""}` : message?.server || "";
  return ["alpi", who, exportStamp(message?.at)].filter(Boolean).join(" · ");
}

export function exportMarkdown(message) {
  const title = exportTitle(message) || "Message";
  return `# ${title}\n_${exportMeta(message)}_\n\n${String(message?.body || "").trim()}\n`;
}

function inline(text) {
  return inlineSegments(String(text ?? "")).map((s) => {
    const v = escapeHtml(s.v);
    if (s.t === "bold") return `<strong>${v}</strong>`;
    if (s.t === "italic") return `<em>${v}</em>`;
    if (s.t === "code") return `<code>${v}</code>`;
    return v;
  }).join("");
}

function block(b) {
  if (b.kind === "chart") return `<figure class="ax-chart">${chartSvg(b.spec)}</figure>`;
  if (b.kind === "heading") return `<h2>${inline(b.text)}</h2>`;
  if (b.kind === "label") return `<h3>${escapeHtml(b.label)}</h3>`;
  if (b.kind === "labelBody") return `<h3>${escapeHtml(b.label)}</h3><p>${inline(b.body)}</p>`;
  if (b.kind === "quote") return `<blockquote>${inline(b.text)}</blockquote>`;
  if (b.kind === "code") return `<pre><code>${escapeHtml(b.text)}</code></pre>`;
  if (b.kind === "table") {
    const head = b.headers.map((h) => `<th>${inline(h)}</th>`).join("");
    const rows = b.rows.map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`).join("");
    return `<table class="ax-table"><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table>`;
  }
  if (b.kind === "list") {
    const tag = b.ordered ? "ol" : "ul";
    const items = b.items.map((it) => (b.ordered ? `<li value="${Math.min(parseInt(it.marker, 10), 2147483647)}">${inline(it.text)}</li>` : it.entry
      ? `<li><strong>${escapeHtml(it.entry.name)}</strong>${it.entry.meta ? ` <span class="ax-dim">${escapeHtml(it.entry.meta)}</span>` : ""}${it.entry.text ? ` — ${inline(it.entry.text)}` : ""}</li>`
      : `<li>${inline(it.text)}</li>`)).join("");
    return `<${tag}>${items}</${tag}>`;
  }
  return b.strong ? `<p><strong>${inline(b.text)}</strong></p>` : `<p>${inline(b.text)}</p>`;
}

function mark(size) {
  const polys = foldPolygons(ALPACA_LOW_FOLD, P.accent, size)
    .map(({ points }) => `<polygon points="${points.map((p) => p.map((v) => v.toFixed(1)).join(",")).join(" ")}" fill="${P.accent}"/>`)
    .join("");
  return `<svg viewBox="0 0 100 100" width="${size}" height="${size}" aria-hidden="true">${polys}</svg>`;
}

const HEX = /^#[0-9a-fA-F]{6}$/;

export function exportCss(accent) {
  const a = HEX.test(String(accent ?? "")) ? accent : P.ink;
  return `
.alpi-export { color: ${P.ink}; background: #ffffff; font-family: ${fontStacks.sans}; font-size: 11pt; line-height: 1.55;
  --chart-1: ${a}; --chart-2: color-mix(in oklch, ${a} 58%, ${P.ink}); --chart-3: color-mix(in oklch, ${a} 40%, #ffffff); --chart-4: color-mix(in oklch, ${a} 55%, ${P.ink3}); }
.alpi-export .ax-head { display: flex; align-items: baseline; gap: 8px; font-size: 9pt; color: ${P.ink3}; }
.alpi-export .ax-head strong { color: ${P.ink}; font-size: 10pt; }
.alpi-export h1 { font-size: 18pt; line-height: 1.25; margin: 10px 0 14px; font-weight: 600; }
.alpi-export h2 { font-size: 13pt; margin: 18px 0 6px; font-weight: 600; break-after: avoid; }
.alpi-export h3 { font-family: ${fontStacks.mono}; font-size: 8pt; letter-spacing: .06em; text-transform: uppercase; color: ${P.ink3}; margin: 14px 0 4px; font-weight: 500; break-after: avoid; }
.alpi-export p { margin: 0 0 8px; }
.alpi-export ul, .alpi-export ol { margin: 0 0 8px; padding-left: 18px; }
.alpi-export li { margin: 2px 0; break-inside: avoid; }
.alpi-export blockquote { margin: 8px 0; padding-left: 10px; border-left: 2px solid ${P.line2}; color: ${P.ink2}; }
.alpi-export code { font-family: ${fontStacks.mono}; font-size: .9em; }
.alpi-export pre { font-family: ${fontStacks.mono}; font-size: 8.5pt; white-space: pre-wrap; word-break: break-word; background: ${P.bgSide}; border: .5px solid ${P.line2}; border-radius: 4px; padding: 8px 10px; margin: 8px 0; }
.alpi-export .ax-table { width: 100%; border-collapse: collapse; font-size: 9.5pt; margin: 8px 0; }
.alpi-export .ax-table th { text-align: left; font-weight: 600; border-bottom: .5px solid ${P.line2}; padding: 4px 6px 4px 0; }
.alpi-export .ax-table td { border-top: .5px solid ${P.line}; padding: 4px 6px 4px 0; vertical-align: top; }
.alpi-export .ax-table tr, .alpi-export figure, .alpi-export pre { break-inside: avoid; }
.alpi-export .ax-dim { color: ${P.ink3}; }
.alpi-export .ax-chart { margin: 12px 0; max-width: 560px; display: flex; flex-direction: column; gap: 6px; }
.alpi-export .ax-chart svg { width: 100%; height: auto; }
.alpi-export .ch-title { font-size: 9.5pt; font-weight: 600; }
.alpi-export .ch-grid { stroke: ${P.line2}; stroke-width: .5; }
.alpi-export .ch-tick, .alpi-export .ch-value { font-family: ${fontStacks.mono}; font-size: 10px; fill: ${P.ink3}; }
.alpi-export .ch-value { fill: ${P.ink}; }
.alpi-export .ch-label { font-size: 11px; fill: ${P.ink2}; }
.alpi-export .ch-line { fill: none; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; stroke: var(--chart-series); }
.alpi-export .ch-line.ch-dashed { stroke-width: 1.5; stroke-dasharray: 3 3; }
.alpi-export .ch-s0 { --chart-series: var(--chart-1); }
.alpi-export .ch-s1 { --chart-series: var(--chart-2); }
.alpi-export .ch-s2 { --chart-series: var(--chart-3); }
.alpi-export .ch-s3 { --chart-series: var(--chart-4); }
.alpi-export .ch-bar, .alpi-export .ch-dot { fill: var(--chart-series); }
.alpi-export .ch-legend { display: flex; flex-wrap: wrap; gap: 4px 12px; font-family: ${fontStacks.mono}; font-size: 8pt; color: ${P.ink2}; }
.alpi-export .ch-key { display: inline-flex; align-items: center; gap: 5px; }
.alpi-export .ch-swatch { width: 9px; height: 9px; border-radius: 2px; background: var(--chart-series); }
.alpi-export .ch-swatch.ch-dashed { width: 12px; height: 0; border-radius: 0; background: none; border-top: 1.5px dashed var(--chart-series); }
.alpi-export .ax-foot { display: flex; align-items: center; gap: 6px; font-family: ${fontStacks.mono}; font-size: 7.5pt; color: ${P.ink3}; border-top: .5px solid ${P.line2}; padding-top: 6px; }
.alpi-export .ax-foot b { font-family: ${fontStacks.sans}; color: ${P.ink}; font-size: 8.5pt; }
@media print {
  @page { margin: 16mm 16mm 16mm; }
}
.alpi-export .ax-sheet { width: 100%; border-collapse: collapse; }
.alpi-export .ax-sheet > tbody > tr > td, .alpi-export .ax-sheet > tfoot > tr > td { padding: 0; }
.alpi-export .ax-sheet > tbody > tr { break-inside: avoid; }
.alpi-export .ax-sheet > tfoot { display: table-footer-group; }
.alpi-export .ax-foot { margin-top: 10px; }`;
}

export function exportArticle(message) {
  const title = exportTitle(message);
  const footer = exportFooter(message).replace(/^alpi(?: · )?/, "");
  const head = `<div class="ax-head"><strong>${escapeHtml(message?.profile ? `@${message.profile}` : "")}</strong><span>${escapeHtml([message?.server, exportStamp(message?.at)].filter(Boolean).join(" · "))}</span></div>`;
  const blocks = parseNotificationBody(message?.body || "");
  const rows = [head + (title ? `<h1>${escapeHtml(title)}</h1>` : "")];
  for (let i = 0; i < blocks.length; i += 1) {
    const leads = blocks[i].kind === "heading" || blocks[i].kind === "label";
    rows.push(leads && i + 1 < blocks.length ? block(blocks[i]) + block(blocks[++i]) : block(blocks[i]));
  }
  return `<article class="alpi-export" data-export-profile="${escapeHtml(message?.profile || "")}" data-export-server="${escapeHtml(message?.server || "")}">`
    + `<table class="ax-sheet"><tbody>${rows.map((r) => `<tr><td>${r}</td></tr>`).join("")}</tbody>`
    + `<tfoot><tr><td><footer class="ax-foot">${mark(11)}<b>alpi</b>${footer ? `<span>· ${escapeHtml(footer)}</span>` : ""}</footer></td></tr></tfoot></table></article>`;
}

export function exportHtml(message, { accent } = {}) {
  const title = escapeHtml(exportTitle(message) || exportFileName(message, "pdf").replace(/\.pdf$/, ""));
  return `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${title}</title>`
    + `<style>html, body { margin: 0; background: #ffffff; } body { padding: 0; }${exportCss(accent)}</style></head><body>${exportArticle(message)}</body></html>`;
}
