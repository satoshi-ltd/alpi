import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import Field from "./Field.jsx";
import { wellStates } from "../../../common/well.mjs";

describe("desktop Field helper and error", () => {
  it("renders a bare input when there is no note", () => {
    const { container } = render(<Field aria-label="Name" />);
    expect(container.querySelector(".ds-field-wrap")).toBeNull();
    expect(screen.getByLabelText("Name")).not.toHaveAttribute("aria-describedby");
  });

  it("describes the input with its helper", () => {
    render(<Field aria-label="Name" helper="Letters, digits and dashes." />);
    const input = screen.getByLabelText("Name");
    const note = document.getElementById(input.getAttribute("aria-describedby"));
    expect(note.textContent).toBe("Letters, digits and dashes.");
    expect(input).not.toHaveAttribute("aria-invalid");
  });

  it("marks the input invalid and announces the error in place of the helper", () => {
    render(<Field aria-label="Name" helper="Letters" error="That name is taken." />);
    const input = screen.getByLabelText("Name");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("alert").textContent).toBe("That name is taken.");
    expect(screen.queryByText("Letters")).toBeNull();
    expect(input.getAttribute("aria-describedby")).toBe(screen.getByRole("alert").id);
  });

  it("keeps a caller's own aria-describedby", () => {
    render(<Field aria-label="Name" aria-describedby="hint" helper="Letters" />);
    expect(screen.getByLabelText("Name").getAttribute("aria-describedby")).toMatch(/^hint \S+$/);
  });

  it("rings an invalid well in the danger fill and fades a disabled one, as the shared recipe says", () => {
    const css = readFileSync(join(import.meta.dirname, "../styles/design-system.css"), "utf8");
    expect(wellStates.error.ring).toBe("danger");
    expect(css).toMatch(/\.ds-field-wrap \{ display: flex;[^}]*width: 100%/);
    expect(css).toMatch(/\[aria-invalid="true"\]:not\(:disabled\):focus \{\s*box-shadow: inset 0 0 0 1px var\(--c-danger\)/);
    expect(wellStates.disabled).toEqual({ surface: "field", edge: "transparent", fade: "disabled" });
    expect(css).toMatch(/\.ds-field:disabled, \.field:disabled \{ background: var\(--well-off\); box-shadow: none; opacity: var\(--alpha-disabled\);/);
    expect(css).toMatch(/\.ds-field:disabled[^{]*\{[^}]*opacity: var\(--alpha-disabled\)/);
    expect(css).toMatch(/\.ds-field-note\.is-error \{ color: var\(--c-danger-text\); \}/);
  });
});
