import React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import ConfirmDelete, { ConfirmDeleteAction } from "./ConfirmDelete.jsx";
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

  it("confirms inside the modal it lives in instead of stacking a second sheet", () => {
    render(
      <Modal title="Account">
        <p>Account body</p>
        <ConfirmDeleteAction
          anchored
          label="Remove account"
          title="Remove it?"
          confirmLabel="Remove"
          onConfirm={vi.fn()}
        />
      </Modal>,
    );
    openConfirm();
    expect(screen.getAllByRole("dialog")).toHaveLength(1);
    expect(screen.getByText("Account body").closest('[style*="display: none"]')).not.toBeNull();
    expect(screen.getByRole("group", { name: "Remove it?" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByText("Account body")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Remove account" })).toBeTruthy();
  });

  it("confirms inside a popover or any ConfirmSheet, never chaining a floating sheet", async () => {
    const onConfirm = vi.fn();
    const { ConfirmSheet } = await import("./ConfirmDelete.jsx");
    const { container } = render(
      <ConfirmSheet inset="12px">
        <span>Peer details</span>
        <ConfirmDeleteAction label="Remove peer" title="Remove peer @pulse?" confirmLabel="Remove" onConfirm={onConfirm} />
      </ConfirmSheet>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Remove peer" }));
    expect(screen.getByText("Peer details").closest('[style*="display: none"]')).not.toBeNull();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(container.querySelector("[data-dialog-footer]")).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
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

  it("keeps the dialog open and busy until an async confirm settles, then closes", async () => {
    let finish;
    const onConfirm = vi.fn(() => new Promise((resolve) => { finish = resolve; }));
    const onClose = vi.fn();
    render(<ConfirmDelete open onClose={onClose} onConfirm={onConfirm} title="Delete it" anchored={false} />);
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Delete" })).toBeDisabled();
    finish();
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  });

  it("stays open for another try when the async confirm fails", async () => {
    const onConfirm = vi.fn(() => Promise.reject(new Error("nope")));
    const onClose = vi.fn();
    render(<ConfirmDelete open onClose={onClose} onConfirm={onConfirm} title="Delete it" anchored={false} />);
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Delete" })).not.toBeDisabled());
    expect(onClose).not.toHaveBeenCalled();
  });

  it("submits the typed confirm on Enter once the text matches", () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();
    render(<ConfirmDelete open onClose={onClose} onConfirm={onConfirm} title="Delete it" typeToConfirm="DELETE" />);
    const field = screen.getByRole("textbox");
    fireEvent.change(field, { target: { value: "DEL" } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(onConfirm).not.toHaveBeenCalled();
    fireEvent.change(field, { target: { value: "DELETE" } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

describe("ConfirmSheet keeps the sheet it borrows", () => {
  function Form() {
    const [value, setValue] = React.useState("");
    return <input aria-label="Key" value={value} onChange={(e) => setValue(e.target.value)} />;
  }

  it("keeps what was typed when the confirm is cancelled", async () => {
    const { ConfirmSheet } = await import("./ConfirmDelete.jsx");
    render(
      <ConfirmSheet>
        <Form />
        <ConfirmDeleteAction label="Remove provider" title="Remove it?" confirmLabel="Remove" onConfirm={vi.fn()} />
      </ConfirmSheet>,
    );
    fireEvent.change(screen.getByLabelText("Key"), { target: { value: "sk-typed" } });
    fireEvent.click(screen.getByRole("button", { name: "Remove provider" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByLabelText("Key").value).toBe("sk-typed");
  });

  it("closes only the confirm on Escape and moves focus into it", async () => {
    const { ConfirmSheet } = await import("./ConfirmDelete.jsx");
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="Account">
        <p>Account body</p>
        <ConfirmDeleteAction label="Remove account" title="Remove it?" confirmLabel="Remove" onConfirm={vi.fn()} />
      </Modal>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Remove account" }));
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Cancel" }));
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByText("Account body")).toBeTruthy();
  });
});
