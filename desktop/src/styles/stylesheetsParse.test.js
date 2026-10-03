import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = join(import.meta.dirname, "..");
const sheets = (dir) => readdirSync(dir).flatMap((name) => {
  const path = join(dir, name);
  return statSync(path).isDirectory() ? sheets(path) : name.endsWith(".css") ? [path] : [];
});

export function braceProblem(css) {
  const code = css.replace(/\/\*[\s\S]*?\*\//g, "").replace(/"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'/g, "");
  let depth = 0;
  for (const [index, char] of [...code].entries()) {
    if (char === "{") depth += 1;
    if (char === "}") depth -= 1;
    if (depth < 0) return `stray } at offset ${index}`;
  }
  return depth === 0 ? null : `${depth} unclosed {`;
}

describe("every stylesheet balances its braces", () => {
  it("catches a stray closing brace", () => {
    expect(braceProblem(".a { color: red; }\n}\n.b { color: blue; }")).toMatch(/stray/);
  });

  it.each(sheets(ROOT).map((path) => [path.slice(ROOT.length + 1), path]))("%s", (_, path) => {
    expect(braceProblem(readFileSync(path, "utf8"))).toBeNull();
  });
});
