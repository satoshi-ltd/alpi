import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { Field, FieldLine } from "./SettingsLayout.jsx";
import { Row } from "../features/settings/primitives.jsx";

const css = readFileSync(join(import.meta.dirname, "SettingsLayout.module.css"), "utf8");
const rule = (selector) => css.match(new RegExp(`${selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*\\{([^}]*)\\}`))?.[1] ?? "";

describe("settings rows share one trailing edge", () => {
  it("right-aligns a wrapper that is the control's only child", () => {
    expect(rule(".fieldControl > :only-child")).toMatch(/justify-content:\s*flex-end/);
  });

  it("lets the trailing ghost button bleed its padding past the edge, sm by 12 and md by 16", () => {
    expect(rule('.fieldControl [data-trailing][data-size="sm"]')).toMatch(/margin-inline-end:\s*calc\(-1 \* var\(--sp-12\)\)/);
    expect(rule('.fieldControl [data-trailing][data-size="md"]')).toMatch(/margin-inline-end:\s*calc\(-1 \* var\(--sp-16\)\)/);
  });

  it("marks only the ghost button that really ends the row", () => {
    const ghost = (label, size = "sm") => <button data-variant="ghost" data-size={size}>{label}</button>;
    const cases = [
      [<><span>6 KB</span>{ghost("Clean")}</>, "Clean"],
      [<span><span>chip</span><span>{ghost("Remove")}<div style={{ position: "absolute" }}><button data-variant="ghost">Confirm</button></div></span></span>, "Remove"],
      [<span><span><span>name</span>{ghost("Edit")}</span></span>, "Edit"],
      [<>{ghost("Add")}<span>chip</span></>, null],
      [<>{ghost("Primary")}<button data-variant="primary">Save</button></>, null],
      [<button data-variant="ghost" data-size="sm" aria-label="Close"></button>, null],
    ];
    for (const [children, expected] of cases) {
      const { container, unmount } = render(<Field label="Row">{children}</Field>);
      const marked = [...container.querySelectorAll("[data-trailing]")].map((b) => b.textContent);
      expect(marked).toEqual(expected ? [expected] : []);
      unmount();
    }
  });

  it("keeps the mark on the button when its confirm opens beside it, so it does not jump", async () => {
    const { container, rerender } = render(<Field label="Logs"><span>{<button data-variant="danger-ghost" data-size="sm">Delete</button>}</span></Field>);
    expect(container.querySelector("[data-trailing]")).toHaveTextContent("Delete");
    rerender(<Field label="Logs"><span><button data-variant="danger-ghost" data-size="sm">Delete</button><div style={{ position: "absolute" }}>Delete logs?</div></span></Field>);
    expect(container.querySelector("[data-trailing]")).toHaveTextContent("Delete");
  });

  it("moves the mark when something solid appears after the button, and skips a hidden last button", async () => {
    const { container } = render(<Field label="Row"><span id="host"><button data-variant="ghost" data-size="sm">Edit</button></span></Field>);
    expect(container.querySelector("[data-trailing]")).toHaveTextContent("Edit");
    const chip = document.createElement("span");
    chip.textContent = "chip";
    container.querySelector("#host").appendChild(chip);
    await new Promise((r) => setTimeout(r, 0));
    expect(container.querySelector("[data-trailing]")).toBeNull();
    const hidden = render(<Field label="Row"><button data-variant="ghost" data-size="sm">Shown</button><button data-variant="ghost" data-size="sm" hidden>Gone</button></Field>);
    expect([...hidden.container.querySelectorAll("[data-trailing]")].map((b) => b.textContent)).toEqual(["Shown"]);
  });

  it("marks the trailing button of each line in a stacked row", () => {
    const { container } = render(
      <Field label="Logs" stacked>
        <FieldLine><span>23 MB</span><button data-variant="ghost" data-size="sm">Clean</button></FieldLine>
        <FieldLine><span><button data-variant="danger-ghost" data-size="sm">Delete run journals</button></span></FieldLine>
      </Field>,
    );
    expect([...container.querySelectorAll("[data-trailing]")].map((b) => b.textContent)).toEqual(["Clean", "Delete run journals"]);
  });

  it("stacks a multi-line row right-aligned with its label on the first line", () => {
    expect(rule(".fieldRowStacked")).toMatch(/align-items:\s*flex-start/);
    expect(rule(".fieldRowStacked .fieldControl")).toMatch(/flex-direction:\s*column[\s\S]*align-items:\s*flex-end/);
    expect(rule(".fieldRowStacked .fieldLabelCol")).toMatch(/padding-top:\s*calc\(\(var\(--ctl-32\) - var\(--text-ui\) \* var\(--lh-ui\)\) \/ 2\)/);
    expect(rule(".fieldLine")).toMatch(/justify-content:\s*flex-end/);
  });

  it("renders a stacked field as right-aligned lines and forwards the helper from Row", () => {
    const { container } = render(
      <Row label="Logs" stacked helper="Run journals are kept for a week.">
        <FieldLine><span>facts</span></FieldLine>
        <FieldLine><span>delete</span></FieldLine>
      </Row>,
    );
    const row = container.querySelector("[data-settings-row]");
    expect(row.className).toMatch(/fieldRowStacked/);
    expect(screen.getByText("Run journals are kept for a week.").className).toMatch(/fieldHelper/);
    expect([...row.querySelectorAll("[class*=fieldLine]")].map((n) => n.textContent)).toEqual(["facts", "delete"]);
  });

  it("leaves a top-aligned row's only child left-aligned", () => {
    expect(rule(".fieldRowTop .fieldControl > :only-child")).toMatch(/justify-content:\s*flex-start/);
  });

  it("keeps a plain field centred", () => {
    const { container } = render(<Field label="Home"><span>x</span></Field>);
    expect(container.firstChild.className).toMatch(/fieldRowCenter/);
  });
});

describe("settings row labels", () => {
  it("are sentence case in source", () => {
    const walk = (dir) => readdirSync(dir).flatMap((name) => {
      const path = join(dir, name);
      if (statSync(path).isDirectory()) return walk(path);
      return /\.jsx$/.test(name) && !/\.test\./.test(name) ? [path] : [];
    });
    const offenders = walk(join(import.meta.dirname, "..", "features")).flatMap((f) =>
      [...readFileSync(f, "utf8").matchAll(/Row label="([^"]*)"/g)].filter((m) => /^[a-z]/.test(m[1])).map((m) => `${f.split("/src/")[1]}: ${m[1]}`));
    expect(offenders).toEqual([]);
  });
});
