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

// Local absolute Unix paths only (macOS/Linux) → data-src; remote/data/relative dropped.
const LOCAL_IMG = /^\/(?!\/)[^\0]*\.(png|jpe?g|webp|gif)$/i;

function basename(p) {
  const s = String(p);
  const i = s.lastIndexOf("/");
  return i >= 0 ? s.slice(i + 1) : s;
}

// Tables get a wrapper (rounded border + scroll); code blocks a language header;
// images become a capped figure with a filename + note caption.
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
    image({ href, title, text }) {
      if (!LOCAL_IMG.test(href || "")) return escapeHtml(text || "");
      const note = (title || text || "").trim();
      const cap = note
        ? `${escapeHtml(basename(href))} · ${escapeHtml(note)}`
        : escapeHtml(basename(href));
      return (
        `<figure class="md-figure">` +
        `<img src="${escapeHtml(href)}" alt="${escapeHtml(text || "")}">` +
        `<figcaption class="md-figcaption">` +
        `<span class="md-figcap">${cap}</span>` +
        `<button type="button" class="md-figdl" aria-label="Download image"></button>` +
        `</figcaption>` +
        `</figure>`
      );
    },
  },
});

DOMPurify.addHook("afterSanitizeAttributes", (node) => {
  if (node.nodeName !== "IMG") return;
  const src = node.getAttribute("src") || "";
  node.removeAttribute("src");
  if (LOCAL_IMG.test(src)) node.setAttribute("data-src", src);
  else node.remove();
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
    "div", "span", "img", "figure", "figcaption", "button",
  ],
  ALLOWED_ATTR: ["class", "align", "src", "alt", "data-src", "type", "aria-label"],
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
