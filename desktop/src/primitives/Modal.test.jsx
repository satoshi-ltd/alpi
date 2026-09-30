import { describe, it, expect } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import Modal from "./Modal.jsx";

describe("Modal focus return", () => {
  it("restores focus to the opener element on close", async () => {
    const opener = document.createElement("button");
    document.body.appendChild(opener);
    opener.focus();
    expect(document.activeElement).toBe(opener);

    const { rerender } = render(
      <Modal open onClose={() => {}}><input autoFocus /></Modal>,
    );
    expect(document.activeElement).not.toBe(opener);

    rerender(<Modal open={false} onClose={() => {}}>x</Modal>);
    await waitFor(() => expect(document.activeElement).toBe(opener));
    opener.remove();
  });
});

describe("Modal content wrapper", () => {
  it("groups all children in one scrollable content region", () => {
    const { getByText } = render(
      <Modal open title="T">
        <div>alpha</div>
        <div>beta</div>
      </Modal>,
    );
    const a = getByText("alpha");
    const b = getByText("beta");
    expect(a.parentElement).toBe(b.parentElement);
    expect(a.parentElement.className).toMatch(/content/);
  });
});

function animationEnd(el) {
  act(() => {
    for (const type of ["animationend", "webkitAnimationEnd"]) el.dispatchEvent(new Event(type, { bubbles: true }));
  });
}

describe("Modal exit", () => {
  it("fades out before unmounting when a controlled modal closes", async () => {
    const { rerender } = render(<Modal open title="Bye"><p>body</p></Modal>);
    rerender(<Modal open={false} title="Bye"><p>body</p></Modal>);
    const backdrop = document.querySelector("[data-closing]");
    expect(backdrop).not.toBeNull();
    expect(backdrop.getAttribute("aria-hidden")).toBe("true");
    expect(backdrop.textContent).toContain("body");
    await waitFor(() => expect(document.querySelector("[data-closing]")).toBeNull());
    expect(document.body.textContent).not.toContain("body");
  });

  it("unmounts as soon as the dialog's own exit animation ends", () => {
    const { rerender } = render(<Modal open aria-label="x"><p>inner</p></Modal>);
    const dialog = document.querySelector('[role="dialog"]');
    rerender(<Modal open={false} aria-label="x"><p>inner</p></Modal>);
    animationEnd(dialog.querySelector("p"));
    expect(document.querySelector("[data-closing]")).not.toBeNull();
    animationEnd(dialog);
    expect(document.querySelector("[data-closing]")).toBeNull();
  });

  it("reopens cleanly when opened again mid-exit", () => {
    const { rerender } = render(<Modal open aria-label="x">a</Modal>);
    rerender(<Modal open={false} aria-label="x">a</Modal>);
    rerender(<Modal open aria-label="x">b</Modal>);
    expect(document.querySelector("[data-closing]")).toBeNull();
    expect(screen.getByRole("dialog").textContent).toContain("b");
  });
});
