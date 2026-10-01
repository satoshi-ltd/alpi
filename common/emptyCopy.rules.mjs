const PROPER = new Set(["MCP", "Ollama", "ALP"]);

function sentenceCase(text) {
  const words = text.split(" ");
  return /^[A-Z]/.test(words[0]) && words.slice(1).every((w) => !/^[A-Z]/.test(w) || PROPER.has(w));
}

export function emptyCopyProblems(entries) {
  const problems = [];
  for (const [key, { title = "", hint = "" }] of Object.entries(entries)) {
    if (!sentenceCase(title)) problems.push(`${key}: title is not sentence case`);
    if (title.endsWith(".")) problems.push(`${key}: title ends with a full stop`);
    if (/ · | — | - |^(none|empty)\b|[!…]|\.\.\./i.test(title)) problems.push(`${key}: title uses none, empty, a dot or dash joiner or loose punctuation`);
    if (!hint) continue;
    if (!/^[A-Z@]/.test(hint)) problems.push(`${key}: hint does not start with a capital`);
    if (!hint.endsWith(".")) problems.push(`${key}: hint does not end with a full stop`);
    if (/[.!?](\s|$)|\s·\s|\s?[—;]\s?|\s-\s|\.\.\./.test(hint.slice(0, -1))) problems.push(`${key}: hint is more than one sentence or joined with a dot, dash or semicolon`);
  }
  return problems;
}
