import { describe, it, expect, vi } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { Scrim, ConnectionPanel } from "./Panels.jsx";

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

  it("ignores Escape and backdrop clicks when not dismissable", () => {
    const onClose = vi.fn();
    const { container } = render(
      <Scrim onClose={onClose} dismissable={false}>
        <div>body</div>
      </Scrim>,
    );
    esc();
    fireEvent.click(container.firstChild);
    expect(onClose).not.toHaveBeenCalled();
  });
});

describe("ConnectionPanel locked", () => {
  it("hides the close button so the only path forward is adding a connection", () => {
    const onClose = vi.fn();
    const { queryByText, rerender } = render(
      <ConnectionPanel open locked={false} onClose={onClose} connections={[]} />,
    );
    expect(queryByText("Close")).toBeTruthy();
    rerender(
      <ConnectionPanel open locked onClose={onClose} connections={[]} />,
    );
    expect(queryByText("Close")).toBeNull();
    esc();
    expect(onClose).not.toHaveBeenCalled();
  });
});
