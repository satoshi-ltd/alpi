import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { RowStateChip } from "../features/Sidebar.jsx";
import { ToolStep } from "../features/ToolSteps.jsx";

const SRC = join(import.meta.dirname, "..");
const read = (rel) => readFileSync(join(SRC, rel), "utf8");
const rule = (rel, selector) => {
  const css = read(rel);
  const at = css.indexOf(`${selector} {`);
  expect(at, `${rel} ${selector}`).toBeGreaterThanOrEqual(0);
  return css.slice(at, css.indexOf("}", at));
};

describe("neutral chrome", () => {
  it.each([
    ["styles/design-system.css", ".alpi-md a"],
    ["primitives/MarkdownBody.module.css", ".body a"],
    ["primitives/Message.module.css", ".md a"],
  ])("%s underlines links so ink still reads as a link", (rel, selector) => {
    const body = rule(rel, selector);
    expect(body).toMatch(/text-decoration: underline;/);
    expect(body).toMatch(/text-decoration-thickness: 1px;/);
    expect(body).toMatch(/text-underline-offset: 2px;/);
  });

  it("weights code keywords apart from identifiers", () => {
    expect(rule("primitives/CodeView.module.css", ".t_keyword")).toMatch(/color: var\(--ink\); font-weight: var\(--fw-semibold\)/);
  });

  it.each([
    ["primitives/Panels.module.css", ".renameInput:focus"],
    ["primitives/EditableSessionTitle.module.css", ".input:focus"],
  ])("%s %s focuses with the shared field line", (rel, selector) => {
    const body = rule(rel, selector);
    expect(body).toMatch(/box-shadow:\s*var\(--field-focus\)/);
    expect(body).not.toMatch(/--accent|--ink\) 14%/);
  });

  it("keeps the composer pill free of any focus ring: the caret is its focus", () => {
    const body = rule("primitives/Composer.module.css", ".body:has(.input:focus)");
    expect(body).toMatch(/outline:\s*none/);
    expect(body).toMatch(/box-shadow:\s*none/);
  });

  it.each(["primitives/Modal.module.css", "primitives/Panels.module.css", "primitives/BrowseModal.module.css", "features/sessions/ManageSessionsModal.module.css"])("%s scrims without blur", (rel) => {
    expect(read(rel)).not.toMatch(/backdrop-filter/);
  });

  it("floats the toast on the float shadow and lets the ink tooltip stand on its fill alone", () => {
    expect(rule("primitives/Notification.module.css", ".toast")).toMatch(/box-shadow: var\(--shadow-float\);/);
    expect(rule("styles/design-system.css", ".ds-tip-body")).not.toMatch(/box-shadow/);
  });

  it("paints a running step in the profile's colour, ink without one", () => {
    expect(rule("features/ToolSteps.module.css", ".step_running .status")).toMatch(/var\(--c, var\(--ink-2\)\)/);
    const { container, rerender } = render(<ToolStep tool={{ name: "read_file", args: {} }} accent="#3899e2" />);
    expect(container.firstElementChild.style.getPropertyValue("--c")).toBe("#3899e2");
    rerender(<ToolStep tool={{ name: "read_file", args: {} }} />);
    expect(container.firstElementChild.style.getPropertyValue("--c")).toBe("");
  });

  it("writes the sidebar state as a word in its kind's text colour, without a dot or the profile's colour", () => {
    render(<RowStateChip state="working" color="#3899e2" />);
    const word = screen.getByText("working");
    expect(word.style.getPropertyValue("--c")).toBe("");
    expect(word.children).toHaveLength(0);
    expect(rule("features/Sidebar.module.css", '.stateChip[data-state="working"]')).toMatch(/color: var\(--ink-2\);/);
    expect(rule("features/Sidebar.module.css", '.stateChip[data-state="needs-you"]')).toMatch(/color: var\(--c-warning-text\);/);
    expect(rule("features/Sidebar.module.css", '.stateChip[data-state="failed"]')).toMatch(/color: var\(--c-danger-text\);/);
    expect(read("features/Sidebar.module.css")).not.toMatch(/\.stateDot/);
  });
});
