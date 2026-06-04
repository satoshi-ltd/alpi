const CODE_EXT = new Set([
  "js", "jsx", "ts", "tsx", "py", "go", "rs", "sh", "sql",
  "json", "yaml", "yml", "html", "htm",
]);
const TEXT_EXT = new Set(["txt", "text", "log", "md", "markdown", "csv"]);

// Allowlist mirror of mobile mimeFor() + alpi/attachments.py; unknown ext → rejected.
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
  return ATTACHMENT_MIME_BY_EXT[ext] || "";
}

export function isSupportedAttachment(name) {
  return attachmentMimeFor(name) !== "";
}

export function fileKind(name, mime) {
  if (String(mime || "").startsWith("image/")) return "image";
  const ext = String(name || "").toLowerCase().split(".").pop();
  if (CODE_EXT.has(ext)) return "code";
  if (TEXT_EXT.has(ext)) return "text";
  if (mime === "application/pdf") return "file";
  if (String(mime || "").startsWith("text/")) return "text";
  return "file";
}

export function fileTypeLabel(name, mime) {
  const sub = String(mime || "").split("/").pop();
  if (sub) return sub;
  return String(name || "").toLowerCase().split(".").pop() || "file";
}

export function fmtSize(n) {
  if (n >= 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  if (n >= 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${n} B`;
}
