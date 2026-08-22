export { fileKind, fileTypeLabel, fmtSize } from "../../../common/fileKind.mjs";

const ATTACHMENT_MIME_BY_EXT = {
  png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg",
  webp: "image/webp", pdf: "application/pdf",
  txt: "text/plain", text: "text/plain", log: "text/plain",
  md: "text/markdown", markdown: "text/markdown",
  csv: "text/csv", json: "application/json",
  yaml: "application/yaml", yml: "application/yaml",
  html: "text/html", htm: "text/html",
  js: "text/plain", jsx: "text/plain", ts: "text/plain", tsx: "text/plain",
  py: "text/plain", go: "text/plain", rs: "text/plain",
  sh: "text/plain", sql: "text/plain",
};

export function attachmentMimeFor(name) {
  const ext = String(name || "").toLowerCase().split(".").pop();
  return ATTACHMENT_MIME_BY_EXT[ext] || "application/octet-stream";
}

export function isSupportedAttachment(name) {
  return !!String(name || "").trim();
}
