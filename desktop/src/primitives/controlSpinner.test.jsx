import { readFileSync } from "node:fs";
import { join } from "node:path";
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Button from "./Button.jsx";
import Chip from "./Chip.jsx";

const css = (name) => readFileSync(join(import.meta.dirname, name), "utf8");

describe("one arc for every control", () => {
  it.each([
    ["Chip md", <Chip activity>paused</Chip>],
    ["Chip sm", <Chip size="sm" activity>paused</Chip>],
    ["Button", <Button loading>Save</Button>],
    ["Button icon", <Button loading icon={<span data-icon />} aria-label="Refresh" />],
  ])("%s draws the shared SpinnerIcon in its own ink", (_, node) => {
    const { container } = render(node);
    const arcs = container.querySelectorAll("svg.ds-spin");
    expect(arcs).toHaveLength(1);
    expect(arcs[0].getAttribute("stroke")).toBe("currentColor");
    expect(arcs[0].getAttribute("aria-hidden")).toBe("true");
    expect(arcs[0].getAttribute("class")).toMatch(/spinner/);
    expect(container.querySelector("span[class*=spinner]")).toBeNull();
    expect(container.querySelector("[data-icon]")).toBeNull();
  });

  it("keeps each control's size and leaves no CSS arc of its own", () => {
    const chip = css("Chip.module.css");
    const button = css("Button.module.css");
    for (const sheet of [chip, button]) {
      expect(sheet).not.toMatch(/@keyframes|chipSpin|btnSpin|border-right-color/);
    }
    expect(chip).toMatch(/\.chip \.spinner\s*\{[^}]*width: var\(--space-5\);[^}]*height: var\(--space-5\);/);
    expect(chip).toMatch(/\.chip\.sm \.spinner\s*\{[^}]*width: var\(--space-3\);[^}]*height: var\(--space-3\);/);
    expect(button).toMatch(/\.button \.spinner\s*\{[^}]*width: var\(--space-5\);[^}]*height: var\(--space-5\);/);
  });
});
