import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import { Scrim } from "./Panels.jsx";

function esc() {
  window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
}

describe("Scrim", () => {
  it("closes on Escape (so every panel built on it gets ESC-to-close)", () => {
    const onClose = vi.fn();
    render(
      <Scrim onClose={onClose}>
        <div>body</div>
      </Scrim>,
    );
    esc();
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("ignores non-Escape keys", () => {
    const onClose = vi.fn();
    render(
      <Scrim onClose={onClose}>
        <div>body</div>
      </Scrim>,
    );
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "a" }));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("removes the listener on unmount", () => {
    const onClose = vi.fn();
    const { unmount } = render(
      <Scrim onClose={onClose}>
        <div>body</div>
      </Scrim>,
    );
    unmount();
    esc();
    expect(onClose).not.toHaveBeenCalled();
  });
});
