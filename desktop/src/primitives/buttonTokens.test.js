import { join } from "node:path";
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { buttonHeights } from "../../../common/button.mjs";

const css = readFileSync(join(import.meta.dirname, "Button.module.css"), "utf8");
const tokens = readFileSync(join(import.meta.dirname, "../styles/tokens.css"), "utf8");

describe("desktop button dimensions", () => {
  it.each(Object.entries(buttonHeights))("matches the shared %s size contract", (size, heights) => {
    const selector = size === "md" ? "button" : size;
    const block = css.match(new RegExp(`\\.${selector} \\{([^}]+)\\}`))[1];
    let value = block.match(/height:\s*([^;]+)/)[1];
    if (value.startsWith("var(")) {
      const token = value.slice(4, -1);
      value = tokens.match(new RegExp(`${token}:\\s*([^;]+)`))[1];
    }
    expect(parseFloat(value)).toBe(heights.desktop);
  });
});
