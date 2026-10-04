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
    ["primitives/Composer.module.css", ".body:has(.input:focus)"],
    ["features/ToolSteps.module.css", ".head:focus-visible"],
    ["features/ToolSteps.module.css", ".bucket:focus-visible"],
    ["primitives/Reasoning.module.css", ".row:focus-visible"],
  ])("%s %s focuses with the shared focus token", (rel, selector) => {
    const body = rule(rel, selector);
    expect(body).toMatch(/var\(--focus-border\)|var\(--well-ring\)/);
    expect(body).not.toMatch(/--accent|--ink\) 14%/);
  });

  it.each(["primitives/Modal.module.css", "primitives/Panels.module.css", "primitives/BrowseModal.module.css", "features/sessions/ManageSessionsModal.module.css"])("%s scrims without blur", (rel) => {
    expect(read(rel)).not.toMatch(/backdrop-filter/);
  });

  it("seams the toast and lifts the tooltip with tokens, never a literal shadow", () => {
    expect(rule("primitives/Notification.module.css", ".toast")).toMatch(/box-shadow: var\(--shadow\);/);
    expect(rule("styles/design-system.css", ".ds-tip-body")).toMatch(/box-shadow: var\(--shadow-sm\);/);
  });

  it("paints a running step in the profile's colour, ink without one", () => {
    expect(rule("features/ToolSteps.module.css", ".step_running .status")).toMatch(/var\(--c, var\(--ink-2\)\)/);
    const { container, rerender } = render(<ToolStep tool={{ name: "read_file", args: {} }} accent="#3899e2" />);
    expect(container.firstElementChild.style.getPropertyValue("--c")).toBe("#3899e2");
    rerender(<ToolStep tool={{ name: "read_file", args: {} }} />);
    expect(container.firstElementChild.style.getPropertyValue("--c")).toBe("");
  });

  it("tints the sidebar working chip with the row's profile colour", () => {
    render(<RowStateChip state="working" color="#3899e2" />);
    expect(screen.getByText("working").style.getPropertyValue("--c")).toBe("#3899e2");
  });
});
