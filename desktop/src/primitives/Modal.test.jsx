import { describe, it, expect } from "vitest";
import { render, waitFor } from "@testing-library/react";
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
