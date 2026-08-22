import { stripPreviewMarkdown } from "../../../common/stripPreviewMarkdown.mjs";

function bodyPreview(row) {
  const line = row?.body?.split("\n").find((it) => stripPreviewMarkdown(it));
  return stripEmoji(stripPreviewMarkdown(line)) || "—";
}

const EMOJI_RE = /[\p{Extended_Pictographic}\u{1F1E6}-\u{1F1FF}\uFE0F\u200D\u{1F3FB}-\u{1F3FF}]/gu;

function stripEmoji(text) {
  return String(text || "").replace(EMOJI_RE, "").replace(/\s{2,}/g, " ").trim();
}

export function headlineParts(row) {
  const explicit = stripEmoji((row?.title || "").trim());
  if (explicit) return { title: explicit, preview: bodyPreview(row) };
  const stripped = stripPreviewMarkdown(row?.body || "");
  const m = stripped.match(/^(.{1,100}?[.!?])\s+(.+)$/);
  if (m) return { title: stripEmoji(m[1].trim()), preview: stripEmoji(m[2].trim()) };
  return { title: stripEmoji(stripped) || "—", preview: "" };
}
