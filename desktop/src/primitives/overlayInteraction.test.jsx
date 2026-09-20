import { useState, StrictMode } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import AlpiPicker from "../features/AlpiPicker.jsx";
import VersionButton from "../features/VersionButton.jsx";

vi.mock("../lib/updater.js", () => ({
  subscribeUpdater: () => () => {},
  checkForUpdates: vi.fn(),
  applyPendingUpdate: vi.fn(),
}));

import Modal from "./Modal.jsx";
import BrowseModal from "./BrowseModal.jsx";
import Dropdown from "./Dropdown.jsx";
import ContextMenu from "./ContextMenu.jsx";
import ConfirmDelete from "./ConfirmDelete.jsx";
import { Palette } from "./Panels.jsx";

function Nested() {
  const [confirm, setConfirm] = useState(false);
  const [open, setOpen] = useState(true);
  return <BrowseModal open={open} title="Schedules" onClose={() => setOpen(false)} list={<button>Job</button>}>
    <button onClick={() => setConfirm(true)}>Remove job</button>
    <ConfirmDelete open={confirm} anchored={false} title="Delete job?" onClose={() => setConfirm(false)} />
  </BrowseModal>;
}

describe("overlay interactions", () => {
  it("Escape dismisses only the confirmation and returns focus to its opener", async () => {
    render(<StrictMode><Nested /></StrictMode>);
    const trigger = screen.getByRole("button", { name: "Remove job" });
    trigger.focus();
    fireEvent.click(trigger);
    expect(screen.getByRole("dialog", { name: "Delete job?" })).toBeTruthy();
    fireEvent.keyDown(document.activeElement, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Delete job?" })).toBeNull();
    expect(screen.getByRole("dialog", { name: "Schedules" })).toBeTruthy();
    await waitFor(() => expect(document.activeElement).toBe(trigger));
    fireEvent.keyDown(trigger, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Schedules" })).toBeNull();
  });

  it("clicking inside a portalled confirmation does not dismiss its browser", () => {
    render(<Nested />);
    fireEvent.click(screen.getByText("Remove job"));
    fireEvent.mouseDown(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByRole("dialog", { name: "Schedules" })).toBeTruthy();
  });

  it.each(["profile", "version"])("Escape closes only the %s popover above a dialog", (kind) => {
    const close = vi.fn();
    render(<StrictMode><Modal open title="Parent" onClose={close}>
      {kind === "profile"
        ? <AlpiPicker profiles={[{ name: "pixel" }]} activeAlpi="pixel" />
        : <VersionButton />}
    </Modal></StrictMode>);
    fireEvent.click(screen.getByRole("button", { name: kind === "profile" ? /pixel/ : "0.0.0" }));
    const panel = () => kind === "profile"
      ? screen.queryByPlaceholderText("Find profile…")
      : screen.queryByText("You're up to date");
    expect(panel()).toBeTruthy();
    fireEvent.keyDown(document.activeElement, { key: "Escape" });
    expect(panel()).toBeNull();
    expect(close).not.toHaveBeenCalled();
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(close).toHaveBeenCalledTimes(1);
  });

  it("keeps earlier popovers open when a newer dialog handles Escape", () => {
    function Scene() {
      const [open, setOpen] = useState(false);
      return <>
        <AlpiPicker profiles={[{ name: "pixel" }]} activeAlpi="pixel" />
        <VersionButton />
        <button onClick={() => setOpen(true)}>Open dialog</button>
        <Modal open={open} title="New dialog" onClose={() => setOpen(false)}>Content</Modal>
      </>;
    }
    render(<Scene />);
    fireEvent.click(screen.getByRole("button", { name: /pixel/ }));
    fireEvent.click(screen.getByRole("button", { name: "0.0.0" }));
    fireEvent.click(screen.getByText("Open dialog"));
    fireEvent.keyDown(document.activeElement, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByPlaceholderText("Find profile…")).toBeTruthy();
    expect(screen.getByText("You're up to date")).toBeTruthy();
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(screen.queryByText("You're up to date")).toBeNull();
    expect(screen.getByPlaceholderText("Find profile…")).toBeTruthy();
  });

  it("keeps Tab inside a dialog, skipping disabled controls", () => {
    render(<><button>Outside</button><Modal open title="Edit"><button>First</button><button disabled>Disabled</button><button>Last</button></Modal></>);
    const first = screen.getByText("First");
    const last = screen.getByText("Last");
    expect(document.activeElement).toBe(first);
    fireEvent.keyDown(first, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(last);
    fireEvent.keyDown(last, { key: "Tab" });
    expect(document.activeElement).toBe(first);
  });

  it("focuses a dialog with no interactive content", () => {
    render(<Modal open title="Working">Please wait</Modal>);
    const dialog = screen.getByRole("dialog", { name: "Working" });
    expect(document.activeElement).toBe(dialog);
    fireEvent.keyDown(dialog, { key: "Tab" });
    expect(document.activeElement).toBe(dialog);
  });

  it("respects an explicit autofocus field", () => {
    render(<Modal open title="Edit"><button>First</button><input aria-label="Name" autoFocus /></Modal>);
    expect(document.activeElement).toBe(screen.getByLabelText("Name"));
  });

  it("orders initially nested dialogs above their parents", () => {
    const outer = vi.fn();
    const inner = vi.fn();
    render(<StrictMode><Modal open title="Outer" onClose={outer}><Modal open title="Inner" onClose={inner}><button>Inner action</button></Modal></Modal></StrictMode>);
    fireEvent.keyDown(document.activeElement, { key: "Escape" });
    expect(inner).toHaveBeenCalledTimes(1);
    expect(outer).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(screen.getByText("Inner action"));
  });

  it("does not let callback rerenders reorder open dialogs", () => {
    const outer = vi.fn();
    const inner = vi.fn();
    const tree = () => <Modal open title="Outer" onClose={() => outer()}><Modal open title="Inner" onClose={() => inner()}>Inner</Modal></Modal>;
    const { rerender } = render(tree());
    rerender(tree());
    fireEvent.keyDown(document.activeElement, { key: "Escape" });
    expect(inner).toHaveBeenCalledTimes(1);
    expect(outer).not.toHaveBeenCalled();
  });

  it("navigates a portalled dropdown without closing its dialog or submitting the form", async () => {
    const close = vi.fn();
    const submit = vi.fn((e) => e.preventDefault());
    render(<Modal open title="Settings" onClose={close}><form onSubmit={submit}>
      <Dropdown trigger={{ label: "Model" }} portal>{({ close }) => <>
        <Dropdown.Row disabled>Unavailable</Dropdown.Row>
        <Dropdown.Row onClick={close}>First model</Dropdown.Row>
        <Dropdown.Row onClick={close}>Last model</Dropdown.Row>
      </>}</Dropdown>
    </form></Modal>);
    const trigger = screen.getByRole("button", { name: "Model" });
    trigger.focus();
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    const first = screen.getByText("First model").closest("button");
    const last = screen.getByText("Last model").closest("button");
    expect(document.activeElement).toBe(first);
    fireEvent.keyDown(first, { key: "ArrowUp" });
    expect(document.activeElement).toBe(last);
    fireEvent.keyDown(last, { key: "Home" });
    expect(document.activeElement).toBe(first);
    fireEvent.keyDown(first, { key: "Escape" });
    expect(close).not.toHaveBeenCalled();
    expect(screen.queryByText("First model")).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(trigger));
    fireEvent.click(trigger);
    fireEvent.click(screen.getByText("Last model"));
    expect(submit).not.toHaveBeenCalled();
  });

  it("context menus skip disabled actions and support End/Home", () => {
    const disabled = vi.fn();
    const picked = vi.fn();
    const close = vi.fn();
    render(<ContextMenu x={0} y={0} onClose={close} items={[
      { label: "Disabled", disabled: true, onClick: disabled },
      { label: "Copy", onClick: picked },
      { kind: "separator" },
      { label: "Delete", kind: "danger" },
    ]} />);
    const copy = screen.getByRole("menuitem", { name: "Copy" });
    expect(document.activeElement).toBe(copy);
    fireEvent.click(screen.getByRole("menuitem", { name: "Disabled" }));
    expect(disabled).not.toHaveBeenCalled();
    expect(close).not.toHaveBeenCalled();
    fireEvent.keyDown(copy, { key: "End" });
    expect(document.activeElement).toBe(screen.getByRole("menuitem", { name: "Delete" }));
    fireEvent.keyDown(document.activeElement, { key: "Home" });
    fireEvent.click(copy);
    expect(picked).toHaveBeenCalledTimes(1);
    expect(close).toHaveBeenCalledTimes(1);
  });

  it("Shift+Tab moves backwards through command palette results", () => {
    const first = vi.fn();
    const second = vi.fn();
    render(<Palette open onClose={() => {}} groups={[{ label: "Actions", items: [
      { id: "first", label: "First", onSelect: first },
      { id: "second", label: "Second", onSelect: second },
    ]}]} />);
    const input = screen.getByRole("textbox");
    fireEvent.keyDown(input, { key: "Tab" });
    fireEvent.keyDown(input, { key: "Tab", shiftKey: true });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(first).toHaveBeenCalledTimes(1);
    expect(second).not.toHaveBeenCalled();
  });
});
