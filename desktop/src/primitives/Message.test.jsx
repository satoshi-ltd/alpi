import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";

import Message, { tintFor } from "./Message.jsx";

describe("tintFor", () => {
  it("turns a hex accent into an rgba tint", () => {
    expect(tintFor("#f0b447", 0.16)).toBe("rgba(240, 180, 71, 0.16)");
  });

  it("mixes a token accent instead of dropping it", () => {
    expect(tintFor("var(--accent)", 0.16)).toBe("color-mix(in srgb, var(--accent) 16%, transparent)");
  });

  it("gives nothing for an empty accent", () => {
    expect(tintFor("")).toBeUndefined();
  });
});

describe("Message", () => {
  it("defaults the accent to the current theme token, not a hardcoded dark amber", () => {
    const { container } = render(<Message header={{ name: "a" }} body="hi" markdown={false} />);
    const dot = container.querySelector("[aria-hidden]");
    expect(dot.getAttribute("style")).toContain("var(--accent)");
    expect(container.innerHTML).not.toContain("240, 180, 71");
  });
});
