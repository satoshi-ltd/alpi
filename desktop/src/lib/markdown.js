import { marked } from "marked";
import DOMPurify from "dompurify";

marked.setOptions({
  gfm: true,
  breaks: true,
});

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// Tables get a wrapper (rounded border + scroll); code blocks a language header.
marked.use({
  renderer: {
    table(token) {
      const cell = (c, tag) =>
        `<${tag}${c.align ? ` align="${c.align}"` : ""}>${this.parser.parseInline(c.tokens)}</${tag}>`;
      const head = token.header.map((c) => cell(c, "th")).join("");
      const body = token.rows
        .map((row) => `<tr>${row.map((c) => cell(c, "td")).join("")}</tr>`)
        .join("");
      return `<div class="md-table"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
    },
    code({ text, lang }) {
      const label = (lang || "").trim().split(/\s+/)[0] || "text";
      return (
        `<div class="md-code">` +
        `<div class="md-code-head"><span class="md-code-lang">${escapeHtml(label)}</span></div>` +
        `<pre><code>${escapeHtml(text)}</code></pre>` +
        `</div>`
      );
    },
  },
});

const PURIFY_OPTS = {
  ALLOWED_TAGS: [
    "p", "br",
    "strong", "b", "em", "i",
    "code", "pre",
    "h1", "h2", "h3", "h4",
    "ul", "ol", "li",
    "blockquote", "hr",
    "table", "thead", "tbody", "tr", "th", "td",
    "div", "span",
  ],
  ALLOWED_ATTR: ["class", "align"],
};

const cache = new Map();
const CACHE_MAX = 500;

export function renderMarkdown(text) {
  if (!text) return "";
  const key = String(text);
  const hit = cache.get(key);
  if (hit !== undefined) return hit;
  const html = DOMPurify.sanitize(marked.parse(key), PURIFY_OPTS);
  if (cache.size >= CACHE_MAX) {
    const firstKey = cache.keys().next().value;
    cache.delete(firstKey);
  }
  cache.set(key, html);
  return html;
}

export function renderMarkdownInline(text) {
  if (!text) return "";
  return DOMPurify.sanitize(marked.parseInline(String(text)), PURIFY_OPTS);
}
