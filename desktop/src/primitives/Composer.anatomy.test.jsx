import { describe, it, expect, vi } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fireEvent, render, screen } from "@testing-library/react";
import Composer from "./Composer.jsx";
import IconBtn from "./IconBtn.jsx";

const css = readFileSync(join(import.meta.dirname, "Composer.module.css"), "utf8");
const rule = (selector) => css.match(new RegExp(`(?:^|\\n)${selector.replace(/[.()[\]:]/g, "\\$&")} \\{([^}]*)\\}`))[1];

describe("Composer anatomy", () => {
  it("is one row: the leading +, the input, the trailing controls and the round send", () => {
    const { container } = render(
      <Composer value="hi" onChange={() => {}} leading={<IconBtn aria-label="Attach files">+</IconBtn>} leftActions={<button type="button">model</button>} />,
    );
    const line = container.querySelector("textarea").parentElement;
    const order = [...line.children].map((el) => el.tagName === "TEXTAREA" ? "input" : el.textContent.includes("+") ? "plus" : el.textContent.includes("model") ? "trailing" : el.tagName);
    expect(order).toEqual(["plus", "input", "trailing"]);
    expect(screen.getByRole("button", { name: "Send" }).closest("div")).toBe(line.lastElementChild);
  });

  it("draws no hint row, and still sends on ⌘↵, which the send tooltip names", () => {
    const onSubmit = vi.fn();
    const { container } = render(<Composer value="hi" onChange={() => {}} onSubmit={onSubmit} />);
    expect(container.textContent).not.toMatch(/send$|mention/);
    expect(css).not.toMatch(/\.hint\b/);
    fireEvent.keyDown(container.querySelector("textarea"), { key: "Enter", metaKey: true });
    expect(onSubmit).toHaveBeenCalled();
    expect(container.querySelector(".ds-tip-body").textContent).toBe("Send (⌘↵)");
  });

  it("is a 56 px pill on the fill at the sheet radius, with a 16 px input and no focus ring", () => {
    expect(rule(".body")).toMatch(/min-height: var\(--composer-h\);/);
    expect(rule(".body")).toMatch(/border-radius: var\(--r-sheet\);/);
    expect(rule(".body")).toMatch(/background: var\(--fill\);/);
    expect(rule(".input")).toMatch(/font-size: var\(--text-read\);/);
    expect(rule(".body:has(.input:focus)")).toMatch(/outline: none;/);
    expect(rule(".input:focus,\n.input:focus-visible")).toMatch(/outline: none;/);
    expect(readFileSync(join(import.meta.dirname, "../styles/tokens.css"), "utf8")).toMatch(/--composer-h: 56px;/);
  });

  it("fades the stream into the composer instead of meeting a line", () => {
    expect(rule(".wrap::before")).toMatch(/background: linear-gradient\(transparent, var\(--bg-pane\)\);/);
    expect(css).not.toMatch(/border-top/);
  });
});
