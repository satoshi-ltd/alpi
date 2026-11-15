import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(import.meta.dirname, "design-system.css"), "utf8");
const rule = (selector) => {
  const at = css.indexOf(selector);
  return at < 0 ? null : css.slice(at, css.indexOf("}", at));
};

describe("name cascade", () => {
  it("sets the name face with the light tone and falls back to ink, outranking the header h1", () => {
    const body = rule(".ds-name, .ds-chat-header .ds-name {");
    expect(body).toMatch(/font-family:\s*var\(--font-name\)/);
    expect(body).toMatch(/font-weight:\s*800/);
    expect(body).toMatch(/color:\s*var\(--name-light, var\(--ink\)\)/);
  });

  it("switches to the dark tone for a forced dark mode with more weight than the header rule, whatever the order", () => {
    expect(rule(':root[data-mode="dark"] .ds-chat-header .ds-name')).toMatch(/color:\s*var\(--name-dark, var\(--ink\)\)/);
  });

  it("switches to the dark tone for a dark system unless light is forced", () => {
    const media = css.slice(css.indexOf("@media (prefers-color-scheme: dark) {\n  :root:not([data-mode=\"light\"]) .ds-name"));
    expect(media).toMatch(/^@media \(prefers-color-scheme: dark\) \{\n {2}:root:not\(\[data-mode="light"\]\) \.ds-name, :root:not\(\[data-mode="light"\]\) \.ds-chat-header \.ds-name \{ color: var\(--name-dark, var\(--ink\)\); \}/);
  });
});
