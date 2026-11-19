import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import Popover from "../primitives/Popover.jsx";
import Dropdown from "../primitives/Dropdown.jsx";
import { ContextMenuMount } from "../primitives/ContextMenu.jsx";
import { Palette } from "../primitives/Panels.jsx";

afterEach(cleanup);

function PopoverHost() {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ position: "relative" }}>
      <button onClick={() => setOpen(true)}>opener</button>
      <Popover open={open} onClose={() => setOpen(false)} navigable role="menu">
        <button>first item</button>
      </Popover>
    </div>
  );
}

function RerenderingHost() {
  const [tick, setTick] = useState(0);
  return (
    <div style={{ position: "relative" }}>
      <Popover open onClose={() => {}} navigable role="menu" key="kept">
        <button onClick={() => setTick((n) => n + 1)}>item {tick}</button>
      </Popover>
    </div>
  );
}

describe.each([false, true])("a closing overlay with reduced motion %s", (reduced) => {
  beforeEach(() => {
    vi.useFakeTimers();
    window.matchMedia = () => ({ matches: reduced, addEventListener() {}, removeEventListener() {} });
  });
  afterEach(() => {
    vi.useRealTimers();
    delete window.matchMedia;
  });

  it("gives focus back to its opener after Escape, during and after the exit", async () => {
    render(<PopoverHost />);
    const opener = screen.getByText("opener");
    opener.focus();
    fireEvent.click(opener);
    expect(document.activeElement.textContent).toBe("first item");
    fireEvent.keyDown(document.activeElement, { key: "Escape" });
    await act(async () => { vi.advanceTimersByTime(5); });
    expect(document.activeElement).toBe(opener);
    await act(async () => { vi.advanceTimersByTime(400); });
    expect(document.activeElement).toBe(opener);
  });

  it("keeps focus inside an overlay that re-renders while it stays open", async () => {
    render(<RerenderingHost />);
    const item = screen.getByText("item 0");
    item.focus();
    fireEvent.click(item);
    await act(async () => { vi.advanceTimersByTime(5); });
    expect(document.activeElement.textContent).toBe("item 1");
  });
});

describe("a dropdown closing with motion on", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
  });
  afterEach(() => {
    vi.useRealTimers();
    delete window.matchMedia;
  });

  it("returns focus to its trigger", async () => {
    render(<Dropdown trigger={{ label: "Model" }}>{({ close }) => <>
      <Dropdown.Row onClick={close}>First model</Dropdown.Row>
      <Dropdown.Row onClick={close}>Last model</Dropdown.Row>
    </>}</Dropdown>);
    const trigger = screen.getByRole("button", { name: "Model" });
    trigger.focus();
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    await act(async () => { vi.advanceTimersByTime(5); });
    expect(document.activeElement).toBe(screen.getByText("First model").closest("button"));
    fireEvent.keyDown(document.activeElement, { key: "Escape" });
    await act(async () => { vi.advanceTimersByTime(400); });
    expect(document.activeElement).toBe(trigger);
  });
});

function PaletteHost() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <textarea aria-label="message" onKeyDown={(e) => { if (e.key === "k") setOpen(true); }} />
      <Palette open={open} onClose={() => setOpen(false)} groups={[]} />
    </>
  );
}

describe("the palette and a context menu closing with motion on", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
  });
  afterEach(() => {
    vi.useRealTimers();
    delete window.matchMedia;
  });

  it("gives the message box back after the palette closes on Escape", async () => {
    render(<PaletteHost />);
    const box = screen.getByLabelText("message");
    box.focus();
    fireEvent.keyDown(box, { key: "k" });
    await act(async () => { vi.advanceTimersByTime(5); });
    expect(document.activeElement).not.toBe(box);
    fireEvent.keyDown(document.activeElement, { key: "Escape" });
    await act(async () => { vi.advanceTimersByTime(5); });
    expect(document.activeElement).toBe(box);
  });

  it("gives focus back to the row a context menu opened from", async () => {
    render(<><button>row</button><ContextMenuMount /></>);
    const row = screen.getByText("row");
    row.focus();
    act(() => window.openContextMenu({ preventDefault() {}, clientX: 10, clientY: 10 }, [{ label: "Pin", onClick: () => {} }]));
    await act(async () => { vi.advanceTimersByTime(5); });
    expect(document.activeElement).not.toBe(row);
    fireEvent.keyDown(document.activeElement, { key: "Escape" });
    await act(async () => { vi.advanceTimersByTime(400); });
    expect(document.activeElement).toBe(row);
  });
});
