import { join } from "node:path";
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { buttonHeights, buttonHover, buttonLabelWeight, buttonPressed, buttonStates } from "../../../common/button.mjs";

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

describe("Button-based triggers follow the size contract", () => {
  const read = (rel) => readFileSync(join(import.meta.dirname, rel), "utf8");

  it.each([
    ["ModelPicker.module.css", "modelPickerTrigger"],
    ["../features/VersionButton.module.css", "installBtn"],
  ])("%s does not pin .%s to a stale height", (file, cls) => {
    expect(read(file)).not.toMatch(new RegExp(`\\.${cls} \\{[^}]*height`));
  });
});

describe("desktop button states follow the shared recipe", () => {
  const block = (selector) => css.match(new RegExp(`(?:^|\\n)${selector.replace(/[.:()]/g, "\\$&")} \\{([^}]+)\\}`))?.[1] ?? "";

  it.each(Object.entries(buttonLabelWeight))("labels %s with the %s weight", (variant, weight) => {
    const own = block(`.${variant}`);
    if (weight === "semibold") expect(own).toMatch(/font-weight:\s*var\(--fw-semibold\)/);
    else expect(own).not.toMatch(/font-weight/);
  });

  const LADDER = {
    primary: { rest: "background", restToken: "--accent", hover: "background:\\s*var\\(--accent-hover\\)", active: "background:\\s*var\\(--accent-pressed\\)" },
    secondary: { rest: "background", restToken: "--fill", hover: "box-shadow:\\s*var\\(--hover-wash\\)", active: "box-shadow:\\s*var\\(--pressed-wash\\)" },
    ghost: { hover: "background:\\s*var\\(--hover\\)", active: "background:\\s*var\\(--pressed\\)" },
  };

  it.each(Object.entries(LADDER))("steps %s through one state fill per state", (variant, steps) => {
    if (steps.restToken) expect(block(`.${variant}`)).toMatch(new RegExp(`background:\\s*var\\(${steps.restToken}\\)`));
    for (const state of ["hover", "active"]) {
      expect(css).toMatch(new RegExp(`\\.${variant}:not\\(:disabled\\):${state}[^{]*\\{[^}]*${steps[state]}`));
    }
  });

  it("derives the fills in tokens.css: primary 86 / 78 % toward the pane, secondary and ghost on the shared state fills", () => {
    expect([buttonHover.primary.amount, buttonPressed.primary.amount]).toEqual([0.86, 0.78]);
    expect([buttonHover.secondary.token, buttonPressed.secondary.token]).toEqual(["hover", "pressed"]);
    expect([buttonHover.ghost.token, buttonPressed.ghost.token]).toEqual(["hover", "pressed"]);
    expect(tokens).toMatch(/--accent-hover:\s*color-mix\(in srgb, var\(--accent\) 86%, var\(--bg-pane\)\);/);
    expect(tokens).toMatch(/--accent-pressed:\s*color-mix\(in srgb, var\(--accent\) 78%, var\(--bg-pane\)\);/);
  });

  it("cuts every button as a pill", () => {
    expect(block(".button")).toMatch(/border-radius:\s*var\(--r-pill\)/);
  });

  it("presses danger toward black", () => {
    expect(css).toMatch(/\.danger:not\(:disabled\):active[^{]*\{[^}]*color-mix\(in srgb, var\(--c-danger\) 76%, black\)/);
  });

  it("fades a disabled button by the alpha token and keeps the label while loading", () => {
    expect(buttonStates).toEqual({ disabled: "alpha", loading: "keepLabel", loadingFades: false });
    expect(css).toMatch(/\.button:disabled:not\(\.loading\) \{[^}]*opacity: var\(--alpha-disabled\)/);
  });
});
