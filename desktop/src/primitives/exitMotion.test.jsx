import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";

import ContextMenu, { ContextMenuMount } from "./ContextMenu.jsx";
import Dropdown from "./Dropdown.jsx";
import Popover from "./Popover.jsx";
import ConfirmDelete from "./ConfirmDelete.jsx";
import useExit from "../hooks/useExit.js";

function motion(reduced) {
  window.matchMedia = vi.fn(() => ({ matches: reduced, addEventListener() {}, removeEventListener() {} }));
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
  delete window.matchMedia;
});

function Probe({ open }) {
  const { mounted, closing } = useExit(open);
  return <span data-testid="probe">{mounted ? (closing ? "closing" : "open") : "gone"}</span>;
}

describe("useExit", () => {
  it("keeps the surface mounted while it leaves, then drops it", () => {
    motion(false);
    const { rerender } = render(<Probe open />);
    rerender(<Probe open={false} />);
    expect(screen.getByTestId("probe")).toHaveTextContent("closing");
    act(() => vi.advanceTimersByTime(200));
    expect(screen.getByTestId("probe")).toHaveTextContent("gone");
  });

  it("returns to open when it reopens mid-exit", () => {
    motion(false);
    const { rerender } = render(<Probe open />);
    rerender(<Probe open={false} />);
    rerender(<Probe open />);
    act(() => vi.advanceTimersByTime(200));
    expect(screen.getByTestId("probe")).toHaveTextContent("open");
  });

  it("leaves at once under reduced motion", () => {
    motion(true);
    const { rerender } = render(<Probe open />);
    rerender(<Probe open={false} />);
    expect(screen.getByTestId("probe")).toHaveTextContent("gone");
  });

  it("leaves at once where there is no media query", () => {
    const { rerender } = render(<Probe open />);
    rerender(<Probe open={false} />);
    expect(screen.getByTestId("probe")).toHaveTextContent("gone");
  });
});

describe("menus leave with an exit", () => {
  it("a dropdown fades out inert and unmounts", () => {
    motion(false);
    render(<Dropdown trigger={{ label: "pick" }}><button>one</button></Dropdown>);
    fireEvent.click(screen.getByText("pick"));
    const menu = screen.getByRole("menu");
    expect(menu).toHaveClass("anim-menu");
    fireEvent.click(screen.getByText("pick"));
    expect(screen.getByRole("menu", { hidden: true })).toHaveClass("anim-menu-out");
    expect(screen.getByRole("menu", { hidden: true })).toHaveAttribute("inert");
    act(() => vi.advanceTimersByTime(200));
    expect(screen.queryByRole("menu", { hidden: true })).toBeNull();
  });

  it("a dropdown opening upward starts below and grows from its bottom edge", () => {
    motion(false);
    vi.spyOn(Element.prototype, "getBoundingClientRect").mockReturnValue({ top: 400, bottom: 440, left: 300, right: 500, width: 200, height: 40 });
    render(<Dropdown direction="up" align="left" trigger={{ label: "pick" }}><button>one</button></Dropdown>);
    fireEvent.click(screen.getByText("pick"));
    const menu = screen.getByRole("menu");
    expect(menu.style.getPropertyValue("--menu-dy")).toBe("4px");
    expect(menu.style.transformOrigin).toBe("bottom left");
  });

  it("a popover fades out inert and unmounts", () => {
    motion(false);
    function Harness() {
      const [open, setOpen] = useState(true);
      return <span style={{ position: "relative" }}><button onClick={() => setOpen(false)}>shut</button><Popover open={open} onClose={() => setOpen(false)} role="menu"><div>panel</div></Popover></span>;
    }
    render(<Harness />);
    fireEvent.click(screen.getByText("shut"));
    const panel = screen.getByText("panel").closest("[role=menu]");
    expect(panel).toHaveClass("anim-menu-out");
    expect(panel).toHaveAttribute("inert");
    act(() => vi.advanceTimersByTime(200));
    expect(screen.queryByText("panel")).toBeNull();
  });

  it("a context menu keeps its items while it leaves", () => {
    motion(false);
    render(<ContextMenuMount />);
    act(() => window.openContextMenu({ preventDefault() {}, clientX: 10, clientY: 10 }, [{ label: "Pin" }]));
    expect(screen.getByRole("menu")).toHaveClass("anim-menu");
    act(() => window.closeContextMenu());
    expect(screen.getByRole("menu", { hidden: true })).toHaveClass("anim-menu-out");
    expect(screen.getByText("Pin")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(200));
    expect(screen.queryByRole("menu", { hidden: true })).toBeNull();
  });

  it("a closing context menu is out of the overlay stack, so Escape no longer reaches it", () => {
    motion(false);
    const onClose = vi.fn();
    const { rerender } = render(<ContextMenu x={0} y={0} items={[{ label: "Pin" }]} onClose={onClose} />);
    rerender(<ContextMenu x={0} y={0} items={[{ label: "Pin" }]} onClose={onClose} closing />);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();
  });

  it("a context menu opened again mid-exit is a fresh menu that takes focus", () => {
    motion(false);
    render(<ContextMenuMount />);
    act(() => window.openContextMenu({ preventDefault() {}, clientX: 10, clientY: 10 }, [{ label: "Pin" }]));
    act(() => window.closeContextMenu());
    act(() => window.openContextMenu({ preventDefault() {}, clientX: 20, clientY: 20 }, [{ label: "Rename" }]));
    expect(screen.getByRole("menu")).toHaveClass("anim-menu");
    expect(screen.getByRole("menuitem", { name: "Rename" })).toHaveFocus();
    expect(screen.queryByText("Pin")).toBeNull();
  });

  it("a dropdown positions from the untransformed size, not the scaled-down first frame", () => {
    motion(false);
    vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockReturnValue(300);
    vi.spyOn(HTMLElement.prototype, "offsetWidth", "get").mockReturnValue(200);
    vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function rect() {
      return this.getAttribute("role") === "menu"
        ? { top: 0, bottom: 0, left: 0, right: 0, width: 196, height: 294 }
        : { top: 500, bottom: 540, left: 300, right: 500, width: 200, height: 40 };
    });
    render(<Dropdown direction="up" portal trigger={{ label: "pick" }}><button>one</button></Dropdown>);
    fireEvent.click(screen.getByText("pick"));
    const menu = screen.getByRole("menu");
    expect(menu.style.top).toBe("194px");
    expect(menu.style.left).toBe("300px");
  });

  it("a confirm popover keeps its typed body until it has left", () => {
    motion(false);
    function Harness() {
      const [open, setOpen] = useState(true);
      return <span style={{ position: "relative" }}><button onClick={() => setOpen(false)}>shut</button><ConfirmDelete open={open} onClose={() => setOpen(false)} title="Remove?" confirmLabel="Remove" onConfirm={() => {}} /></span>;
    }
    render(<Harness />);
    const before = screen.getByText("Remove?");
    fireEvent.click(screen.getByText("shut"));
    expect(screen.getByText("Remove?")).toBe(before);
    act(() => vi.advanceTimersByTime(200));
    expect(screen.queryByText("Remove?")).toBeNull();
  });
});
