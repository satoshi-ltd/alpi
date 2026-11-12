import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import Pill from "./Pill.jsx";
import { countBadgeSpec } from "../../../common/countBadge.mjs";

const read = (rel) => readFileSync(join(import.meta.dirname, "..", rel), "utf8");

describe("one chip rule", () => {
  it("renders Pill through Chip, with Chip's dot and states", () => {
    const { container } = render(<Pill state="err">failed</Pill>);
    const chip = container.firstChild;
    expect(chip.className).toMatch(/chip/);
    expect(chip.className).toMatch(/errorState/);
    expect(chip.querySelector("span[class*='dot']")).not.toBeNull();
  });

  it("leaves no state-pill rules outside Chip", () => {
    expect(read("styles/design-system.css")).not.toMatch(/\.ds-pill|\.pill\b/);
    expect(existsSync(join(import.meta.dirname, "StatusPill.jsx"))).toBe(false);
  });

  it("sizes the count badge from --badge-size, mono 600, as the shared spec says", () => {
    const flag = read("primitives/BrowseModal.module.css").match(/\.flag \{([^}]*)\}/)[1];
    expect(flag).toMatch(/min-width: var\(--badge-size\)/);
    expect(flag).toMatch(/height: var\(--badge-size\)/);
    expect(flag).toMatch(/font-family: var\(--font-mono\)/);
    expect(flag).toMatch(new RegExp(`font-weight: ${countBadgeSpec.weight}`));
    expect(read("styles/tokens.css")).toMatch(new RegExp(`--badge-size: ${countBadgeSpec.size.desktop}px`));
  });
});
