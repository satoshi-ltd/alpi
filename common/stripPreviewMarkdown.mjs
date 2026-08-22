export function stripPreviewMarkdown(text) {
  return String(text || "")
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/`{1,3}/g, "")
    .replace(/[*_~>#-]+/g, "")
    .replace(/\s+/g, " ")
    .trim();
}
