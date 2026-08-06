import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { ConfirmDeleteAction } from "./ConfirmDelete.jsx";
import Modal from "./Modal.jsx";

function renderAction(props = {}) {
  return render(
    <ConfirmDeleteAction
      label="Remove account"
      title="Remove it?"
      confirmLabel="Remove"
      onConfirm={props.onConfirm ?? vi.fn()}
      {...props}
    />,
  );
}

function openConfirm() {
  const trigger = screen.getByRole("button", { name: "Remove account" });
  fireEvent.click(trigger);
  return trigger;
}

describe("ConfirmDeleteAction", () => {
  it("anchors the confirm next to its trigger by default", () => {
    renderAction();
    const trigger = openConfirm();
    const confirm = screen.getByRole("button", { name: "Remove" });
    expect(trigger.parentElement.contains(confirm)).toBe(true);
  });

  it("escapes the trigger's subtree when not anchored, so a scrolling ancestor cannot clip it", () => {
    renderAction({ anchored: false });
    const trigger = openConfirm();
    const confirm = screen.getByRole("button", { name: "Remove" });
    expect(trigger.parentElement.contains(confirm)).toBe(false);
  });

  it("still confirms and closes when it is not anchored", () => {
    const onConfirm = vi.fn();
    renderAction({ anchored: false, onConfirm });
    openConfirm();
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: "Remove" })).toBeNull();
  });

  it("keeps the confirm reachable from inside a modal", () => {
    render(
      <Modal title="Account">
        <ConfirmDeleteAction
          anchored={false}
          label="Remove account"
          title="Remove it?"
          confirmLabel="Remove"
          onConfirm={vi.fn()}
        />
      </Modal>,
    );
    const trigger = openConfirm();
    const confirm = screen.getByRole("button", { name: "Remove" });
    const scrollingBody = trigger.closest("div[class*='content']");
    expect(scrollingBody).not.toBeNull();
    expect(scrollingBody.contains(confirm)).toBe(false);
  });
});

describe("ConfirmDelete surfaces", () => {
  it("asking for typed text forces the centered dialog even when anchored", () => {
    renderAction({ typeToConfirm: "abby", confirmLabel: "Delete @abby" });
    const trigger = openConfirm();
    const confirm = screen.getByRole("button", { name: "Delete @abby" });
    expect(trigger.parentElement.contains(confirm)).toBe(false);
  });

  it("arms the destructive button only on an exact match", () => {
    const onConfirm = vi.fn();
    renderAction({ typeToConfirm: "abby", confirmLabel: "Delete @abby", onConfirm });
    openConfirm();
    const confirm = screen.getByRole("button", { name: "Delete @abby" });
    expect(confirm).toBeDisabled();

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "abb" } });
    expect(confirm).toBeDisabled();

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "abby" } });
    expect(confirm).not.toBeDisabled();
    fireEvent.click(confirm);
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("marks the dialog surface so the modal drops the popover padding", () => {
    const { unmount } = renderAction();
    openConfirm();
    expect(screen.getByText("Remove it?").closest("div[class*='body']").className)
      .not.toMatch(/inModal/);
    unmount();

    renderAction({ anchored: false });
    openConfirm();
    expect(screen.getByText("Remove it?").closest("div[class*='body']").className)
      .toMatch(/inModal/);
  });
});
