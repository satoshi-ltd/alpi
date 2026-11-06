import { join } from "node:path";
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { buttonHeights, buttonLabelWeight, buttonPressed, buttonStates } from "../../../common/button.mjs";

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

  it.each(Object.entries(buttonPressed))("presses %s with the shared mix", (variant, recipe) => {
    if (recipe.token) {
      expect(css).toMatch(new RegExp(`\\.${variant}:not\\(:disabled\\):active \\{[^}]*background: var\\(--${recipe.token}\\)`));
      return;
    }
    const pct = Math.round(recipe.amount * 100);
    const from = recipe.from === "danger" ? "--c-danger" : "--ink";
    const toward = recipe.toward === "black" ? "black" : "var\\(--bg-pane\\)";
    expect(css).toMatch(new RegExp(`\\.${variant}:not\\(:disabled\\):active[^{]*\\{[^}]*color-mix\\(in srgb, var\\(${from}\\) ${pct}%, ${toward}\\)`));
  });

  it("fades a disabled button by the alpha token and keeps the label while loading", () => {
    expect(buttonStates).toEqual({ disabled: "alpha", loading: "keepLabel", loadingFades: false });
    expect(css).toMatch(/\.button:disabled:not\(\.loading\) \{[^}]*opacity: var\(--alpha-disabled\)/);
  });
});
