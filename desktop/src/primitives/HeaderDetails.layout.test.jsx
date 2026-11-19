import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(import.meta.dirname, "ChatHeader.module.css"), "utf8");
const rule = (name) => css.match(new RegExp(`\\.${name}\\s*\\{([^}]*)\\}`))?.[1] ?? "";

describe("profile details popover layout", () => {
  it("is as wide as the large popover token", () => {
    expect(rule("menu")).toMatch(/min-width:\s*var\(--pop-lg\)/);
  });

  it("keeps every label and value on one line, the label as the fixed side", () => {
    expect(rule("detailLabel")).toMatch(/white-space:\s*nowrap/);
    expect(rule("detailLabel")).toMatch(/flex-shrink:\s*0/);
    expect(rule("detailValue")).toMatch(/white-space:\s*nowrap/);
    expect(rule("detailValue")).toMatch(/flex:\s*1/);
    expect(rule("detailValue")).not.toMatch(/overflow:\s*hidden/);
    expect(rule("menu")).toMatch(/max-width:/);
  });

  it("cuts only the text of a long model or provider name, never the meters and their tips", () => {
    const own = readFileSync(join(import.meta.dirname, "HeaderDetails.module.css"), "utf8");
    const clip = own.match(/\.clip\s*\{([^}]*)\}/)?.[1] ?? "";
    expect(clip).toMatch(/text-overflow:\s*ellipsis/);
    expect(clip).toMatch(/min-width:\s*0/);
  });
});
