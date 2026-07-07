const KEYWORDS = new Set([
  "False", "None", "True", "and", "as", "assert", "async", "await", "break",
  "class", "continue", "def", "del", "elif", "else", "except", "finally",
  "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal",
  "not", "or", "pass", "raise", "return", "try", "while", "with", "yield",
  "match", "case",
]);

const BUILTINS = new Set([
  "self", "cls", "print", "len", "range", "int", "str", "float", "bool",
  "list", "dict", "set", "tuple", "bytes", "open", "isinstance", "issubclass",
  "enumerate", "zip", "map", "filter", "sorted", "reversed", "sum", "min",
  "max", "abs", "any", "all", "super", "type", "repr", "hasattr", "getattr",
  "setattr", "Exception", "ValueError", "TypeError", "KeyError", "RuntimeError",
]);

const HIGHLIGHT_MAX_BYTES = 200_000;

function isWord(c) {
  return c === "_" || (c >= "0" && c <= "9") || (c >= "a" && c <= "z") || (c >= "A" && c <= "Z");
}

export function highlightPython(code) {
  const src = String(code || "");
  const n = src.length;
  const tokens = [];
  const push = (text, type) => { if (text) tokens.push(type ? { text, type } : { text }); };
  let i = 0;
  let prevWord = null;

  while (i < n) {
    const ch = src[i];

    if (ch === "#") {
      let j = i + 1;
      while (j < n && src[j] !== "\n") j += 1;
      push(src.slice(i, j), "comment");
      i = j;
      continue;
    }

    if ((ch === '"' || ch === "'") && src[i + 1] === ch && src[i + 2] === ch) {
      const q = src.slice(i, i + 3);
      let j = i + 3;
      while (j < n && src.slice(j, j + 3) !== q) {
        if (src[j] === "\\") j += 1;
        j += 1;
      }
      j = j < n ? j + 3 : n;
      push(src.slice(i, j), "string");
      i = j;
      prevWord = null;
      continue;
    }

    if (ch === '"' || ch === "'") {
      let j = i + 1;
      while (j < n && src[j] !== ch && src[j] !== "\n") {
        if (src[j] === "\\") j += 1;
        j += 1;
      }
      if (j < n && src[j] === ch) j += 1;
      push(src.slice(i, j), "string");
      i = j;
      prevWord = null;
      continue;
    }

    if (ch === "@") {
      let k = i - 1;
      while (k >= 0 && (src[k] === " " || src[k] === "\t")) k -= 1;
      if (k < 0 || src[k] === "\n") {
        let j = i + 1;
        while (j < n && (isWord(src[j]) || src[j] === ".")) j += 1;
        push(src.slice(i, j), "decorator");
        i = j;
        prevWord = null;
        continue;
      }
    }

    if ((ch >= "0" && ch <= "9") || (ch === "." && src[i + 1] >= "0" && src[i + 1] <= "9")) {
      let j = i;
      while (j < n && /[0-9a-fA-F_.xXoObBjJeE]/.test(src[j])) j += 1;
      if ((src[j] === "+" || src[j] === "-") && /[eE]/.test(src[j - 1])) {
        j += 1;
        while (j < n && (src[j] >= "0" && src[j] <= "9")) j += 1;
      }
      push(src.slice(i, j), "number");
      i = j;
      prevWord = null;
      continue;
    }

    if (isWord(ch) && !(ch >= "0" && ch <= "9")) {
      let j = i + 1;
      while (j < n && isWord(src[j])) j += 1;
      const word = src.slice(i, j);
      const next = src[j];
      if ((next === '"' || next === "'") && /^[rbfu]{1,2}$/i.test(word)) {
        push(word, "string");
        i = j;
        prevWord = null;
        continue;
      }
      let type = null;
      if (KEYWORDS.has(word)) type = "keyword";
      else if (prevWord === "def" || prevWord === "class") type = "def";
      else if (BUILTINS.has(word)) type = "builtin";
      push(word, type);
      prevWord = word === "def" || word === "class" ? word : null;
      i = j;
      continue;
    }

    if (ch === " " || ch === "\t") {
      let j = i;
      while (j < n && (src[j] === " " || src[j] === "\t")) j += 1;
      push(src.slice(i, j), null);
      i = j;
      continue;
    }

    if (ch === "\n") {
      push("\n", null);
      i += 1;
      prevWord = null;
      continue;
    }

    push(ch, null);
    i += 1;
    prevWord = null;
  }
  return tokens;
}

export function toLines(tokens) {
  const lines = [[]];
  for (const t of tokens) {
    const parts = t.text.split("\n");
    for (let k = 0; k < parts.length; k += 1) {
      if (k > 0) lines.push([]);
      if (parts[k]) {
        lines[lines.length - 1].push(
          t.type ? { text: parts[k], type: t.type } : { text: parts[k] },
        );
      }
    }
  }
  return lines;
}

export function codeLines(text, lang) {
  const src = String(text || "");
  if (lang === "py" && src.length <= HIGHLIGHT_MAX_BYTES) {
    return toLines(highlightPython(src));
  }
  return src.split("\n").map((l) => (l ? [{ text: l }] : []));
}
