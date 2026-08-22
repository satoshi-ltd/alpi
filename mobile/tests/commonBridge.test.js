import { execFileSync } from "node:child_process";
import { readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { describe, expect, it } from "vitest";
import { pluralize } from "../../common/pluralize.mjs";

const commonDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../common");

describe("common/ shared source directory", () => {
  it("resolves a module that lives outside the mobile root", () => {
    expect(typeof pluralize).toBe("function");
  });

  it("selects singular only for exactly one", () => {
    expect(pluralize(1, "tool call")).toBe("tool call");
    expect(pluralize(0, "tool call")).toBe("tool calls");
    expect(pluralize(2, "tool call")).toBe("tool calls");
  });

  it("honours an explicit plural form", () => {
    expect(pluralize(1, "entry", "entries")).toBe("entry");
    expect(pluralize(3, "entry", "entries")).toBe("entries");
  });

  it("stays loadable as ESM by bare node, which has no package.json type field to read here", () => {
    const target = pathToFileURL(path.join(commonDir, "pluralize.mjs")).href;
    const out = execFileSync(
      process.execPath,
      [
        "--no-experimental-detect-module",
        "--input-type=module",
        "-e",
        `import { pluralize } from ${JSON.stringify(target)}; process.stdout.write(pluralize(2, "task"));`,
      ],
      { encoding: "utf8" },
    );
    expect(out).toBe("tasks");
  });

  it("carries the module format in every filename, since no package.json may declare it", () => {
    const stray = readdirSync(commonDir).filter((f) => !/\.(mjs|jsx)$/.test(f));
    expect(stray).toEqual([]);
  });

  it("loads every shared logic module under bare node with syntax detection off", () => {
    const mjs = readdirSync(commonDir).filter((f) => f.endsWith(".mjs"));
    expect(mjs.length).toBeGreaterThan(1);
    for (const file of mjs) {
      const target = pathToFileURL(path.join(commonDir, file)).href;
      expect(() => execFileSync(
        process.execPath,
        [
          "--no-experimental-detect-module",
          "--input-type=module",
          "-e",
          `await import(${JSON.stringify(target)});`,
        ],
        { encoding: "utf8", stdio: "pipe" },
      ), file).not.toThrow();
    }
  });
});
