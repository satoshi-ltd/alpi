import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const css = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const tokens = css("../styles/tokens.css");
const tier = (source) => {
  const name = source.match(/z-index:\s*var\((--[\w-]+)\)/)[1];
  return Number(tokens.match(new RegExp(`${name}:\\s*(\\d+)`))[1]);
};

describe("overlay layout", () => {
  it("keeps confirmation dialogs above browser panels", () => {
    expect(tier(css("./Modal.module.css"))).toBeGreaterThan(tier(css("./BrowseModal.module.css")));
    expect(tier(css("./Modal.module.css"))).toBeGreaterThan(tier(css("./Panels.module.css")));
  });

  it.each(["Modal", "BrowseModal"])("constrains %s to the viewport at increased zoom", (name) => {
    const source = css(`./${name}.module.css`);
    expect(source).toMatch(/min-width:\s*0;/);
    expect(source).toMatch(/max-width:\s*calc\(100vw - var\(--space-10\)\)/);
    expect(source).toMatch(/max-height:\s*calc\(100vh - var\(--space-10\)\)/);
  });
});
