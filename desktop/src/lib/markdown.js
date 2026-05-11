import { marked } from "marked";
import DOMPurify from "dompurify";

marked.setOptions({
  gfm: true,
  breaks: true,
});

const cache = new Map();
const CACHE_MAX = 500;

export function renderMarkdown(text) {
  if (!text) return "";
  const key = String(text);
  const hit = cache.get(key);
  if (hit !== undefined) return hit;
  const html = DOMPurify.sanitize(marked.parse(key));
  if (cache.size >= CACHE_MAX) {
    const firstKey = cache.keys().next().value;
    cache.delete(firstKey);
  }
  cache.set(key, html);
  return html;
}

export function renderMarkdownInline(text) {
  if (!text) return "";
  return DOMPurify.sanitize(marked.parseInline(String(text)));
}
