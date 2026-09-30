import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import KeyHint from "./KeyHint.jsx";

const chips = (container) => Array.from(container.querySelectorAll("[aria-hidden]")).map((n) => n.textContent);

describe("KeyHint", () => {
  it("renders one chip per key token", () => {
    expect(chips(render(<KeyHint hint="⌘1–9" />).container)).toEqual(["⌘", "1–9"]);
    expect(chips(render(<KeyHint hint="⇧⌘H" />).container)).toEqual(["⇧", "⌘", "H"]);
  });

  it("renders a prose hint as muted text with no chips", () => {
    const { container } = render(<KeyHint hint="light · dark · system" />);
    expect(chips(container)).toEqual([]);
    expect(container.textContent).toBe("light · dark · system");
  });
});
