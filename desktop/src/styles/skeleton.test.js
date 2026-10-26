import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const read = (f) => readFileSync(join(import.meta.dirname, "..", f), "utf8");
const css = read("primitives/Skeleton.module.css");
const reduced = css.slice(css.indexOf("@media (prefers-reduced-motion: reduce)"));

describe("skeleton paint", () => {
  it("is flat line ink with no gradient, shimmer or blur", () => {
    expect(css).not.toMatch(/gradient|shimmer|blur|background-position/i);
    for (const cls of [".skeleton", ".skLine", ".skMark", ".bone"]) {
      const body = css.match(new RegExp(`(?:^|\\n)\\${cls}\\s*\\{([^}]*)\\}`))[1];
      expect(body).toMatch(/background:\s*var\(--line\)/);
      expect(body).toMatch(/animation:\s*skBreathe var\(--dur-skeleton\) ease-in-out infinite/);
    }
  });

  it("breathes opacity 0.55 to 1 over 1.6 s", () => {
    expect(read("styles/tokens.css")).toMatch(/--dur-skeleton:\s*1\.6s;/);
    const frames = css.match(/@keyframes skBreathe\s*\{([\s\S]*?)\n\}/)[1];
    expect(frames).toMatch(/0%,\s*100%\s*\{\s*opacity:\s*0\.55/);
    expect(frames).toMatch(/50%\s*\{\s*opacity:\s*1/);
  });

  it("staggers lines 90 ms apart", () => {
    const src = read("primitives/Skeleton.jsx");
    expect(src).toMatch(/i \* 0\.09/);
    expect(src).not.toMatch(/i \* 0\.12/);
  });

  it("is static at full opacity under reduced motion", () => {
    expect(reduced).toMatch(/\.bone/);
    expect(reduced).toMatch(/animation:\s*none;\s*opacity:\s*1/);
    expect(reduced).toMatch(/\.reveal\s*\{\s*animation:\s*none/);
  });

  it("fades content in over 120 ms", () => {
    expect(read("styles/tokens.css")).toMatch(/--dur-1:\s*120ms/);
    expect(css).toMatch(/\.reveal\s*\{\s*animation:\s*skReveal var\(--dur-1\)/);
  });
});
