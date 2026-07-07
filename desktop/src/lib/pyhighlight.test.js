import { describe, it, expect } from "vitest";
import { highlightPython, toLines, codeLines } from "./pyhighlight.js";

const typed = (code) =>
  highlightPython(code).filter((t) => t.type).map((t) => [t.type, t.text]);

describe("highlightPython", () => {
  it("tags keywords, def names, strings, numbers and comments", () => {
    const t = typed('def greet(n):\n    return "hi" * 3  # note');
    expect(t).toContainEqual(["keyword", "def"]);
    expect(t).toContainEqual(["def", "greet"]);
    expect(t).toContainEqual(["keyword", "return"]);
    expect(t).toContainEqual(["string", '"hi"']);
    expect(t).toContainEqual(["number", "3"]);
    expect(t).toContainEqual(["comment", "# note"]);
  });

  it("keeps a triple-quoted string as one token across newlines", () => {
    const t = highlightPython('x = """a\nb"""\ny = 1');
    const str = t.find((tok) => tok.type === "string");
    expect(str.text).toBe('"""a\nb"""');
  });

  it("does not treat a hash inside a string as a comment", () => {
    const t = typed('s = "a # b"');
    expect(t).toContainEqual(["string", '"a # b"']);
    expect(t.some(([type]) => type === "comment")).toBe(false);
  });

  it("tags decorators only at line start", () => {
    const t = typed("@cache\ndef f(): pass");
    expect(t).toContainEqual(["decorator", "@cache"]);
  });

  it("preserves exact source when tokens are concatenated", () => {
    const src = 'import os\n\nclass A:\n    v = 0xFF  # hex\n    s = f"{v}"\n';
    const joined = highlightPython(src).map((t) => t.text).join("");
    expect(joined).toBe(src);
  });

  it("reconstructs the original text through toLines", () => {
    const src = "a = 1\nb = 2\n\nc = 3";
    const rebuilt = toLines(highlightPython(src))
      .map((line) => line.map((t) => t.text).join(""))
      .join("\n");
    expect(rebuilt).toBe(src);
  });
});

describe("codeLines", () => {
  it("splits plain text one entry per line without highlighting", () => {
    const lines = codeLines("alpha\nbeta", "text");
    expect(lines).toEqual([[{ text: "alpha" }], [{ text: "beta" }]]);
  });

  it("returns an empty token array for blank lines", () => {
    const lines = codeLines("x = 1\n\ny = 2", "py");
    expect(lines[1]).toEqual([]);
    expect(lines).toHaveLength(3);
  });

  it("highlights only when the language is python", () => {
    expect(codeLines("def f(): pass", "text")).toEqual([[{ text: "def f(): pass" }]]);
    expect(codeLines("def f(): pass", "py").flat().some((t) => t.type === "keyword")).toBe(true);
  });
});
