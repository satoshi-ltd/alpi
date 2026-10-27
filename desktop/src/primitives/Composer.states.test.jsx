import { describe, it, expect, vi } from "vitest";
import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import Composer from "./Composer.jsx";

const css = readFileSync(join(import.meta.dirname, "Composer.module.css"), "utf8");

const PEERS = [
  { id: "ana", hint: "Ana at work", status: "on" },
  { id: "bo", hint: "bo", status: "on" },
];

function mount(props = {}) {
  return render(<Composer value="" onChange={() => {}} onSubmit={() => {}} {...props} />);
}

function typeAt(textarea, value) {
  fireEvent.change(textarea, { target: { value } });
  textarea.setSelectionRange(value.length, value.length);
  fireEvent.select(textarea);
}

function Controlled(props) {
  const [value, setValue] = useState("");
  return <Composer value={value} onChange={setValue} onSubmit={() => {}} {...props} />;
}

describe("Composer reason", () => {
  it("keeps the reason visible with typed text and runs the action", () => {
    const onAction = vi.fn();
    mount({ value: "typed", disabled: true, reason: "Profile paused", reasonAction: "Resume", onReasonAction: onAction });
    expect(screen.getByRole("status")).toHaveTextContent("Profile paused");
    fireEvent.click(screen.getByRole("button", { name: "Resume" }));
    expect(onAction).toHaveBeenCalledTimes(1);
  });

  it("omits the action button when none is given", () => {
    mount({ reason: "Daemon offline — sending paused" });
    expect(screen.queryByRole("button", { name: "Resume" })).toBeNull();
  });

  it("dims only the input and the controls, never the whole body or the reason", () => {
    expect(css).not.toMatch(/\.body\[data-disabled="true"\]\s*\{[^}]*opacity/);
    expect(css).toMatch(/\.body\[data-disabled="true"\] \.input,\s*\.body\[data-disabled="true"\] \.row\s*\{[^}]*opacity:\s*0\.6/);
    expect(css).not.toMatch(/\.reason\s*\{[^}]*(opacity|pointer-events)/);
  });
});

describe("Composer mentions", () => {
  it("stays closed when the composer has no mentions feature", () => {
    const { container } = render(<Controlled />);
    typeAt(container.querySelector("textarea"), "@");
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("says there are no peers instead of closing", () => {
    const { container } = render(<Controlled mentions={[]} />);
    typeAt(container.querySelector("textarea"), "@");
    expect(screen.getByRole("listbox")).toHaveTextContent("No peers yet. Add one in Connections.");
  });

  it("says nothing matches when the query filters every peer out", () => {
    const { container } = render(<Controlled mentions={PEERS} />);
    typeAt(container.querySelector("textarea"), "@zz");
    expect(screen.getByRole("listbox")).toHaveTextContent("No peer matches @zz");
  });

  it("links the textarea to the popover and its active row", () => {
    const { container } = render(<Controlled mentions={PEERS} />);
    const ta = container.querySelector("textarea");
    expect(ta).not.toHaveAttribute("aria-controls");
    typeAt(ta, "@");
    const listbox = screen.getByRole("listbox");
    expect(ta.getAttribute("aria-controls")).toBe(listbox.id);
    const options = screen.getAllByRole("option");
    expect(ta.getAttribute("aria-activedescendant")).toBe(options[0].id);
    fireEvent.keyDown(ta, { key: "ArrowDown" });
    expect(ta.getAttribute("aria-activedescendant")).toBe(options[1].id);
  });

  it("scrolls the keyboard-active row into view", () => {
    const scroll = vi.fn();
    Element.prototype.scrollIntoView = scroll;
    const { container } = render(<Controlled mentions={PEERS} />);
    const ta = container.querySelector("textarea");
    typeAt(ta, "@");
    scroll.mockClear();
    fireEvent.keyDown(ta, { key: "ArrowDown" });
    expect(scroll).toHaveBeenCalledWith({ block: "nearest" });
    delete Element.prototype.scrollIntoView;
  });

  it("shows the alias as a caption only when it differs from the id", () => {
    const { container } = render(<Controlled mentions={PEERS} />);
    typeAt(container.querySelector("textarea"), "@");
    expect(screen.getByText("Ana at work")).toBeInTheDocument();
    expect(screen.getAllByText("bo")).toHaveLength(1);
  });

  it("draws the popover on the edge shadow", () => {
    expect(css).toMatch(/\.mentionPopover\s*\{[^}]*box-shadow:\s*var\(--shadow-edge-sm\)/);
  });
});

describe("Composer focusOnOpen", () => {
  it("focuses the field when nothing else holds focus", () => {
    mount({ focusOnOpen: "doc" });
    expect(document.activeElement).toBe(screen.getByRole("textbox"));
  });

  it("leaves focus alone when another control holds it", () => {
    const other = document.createElement("input");
    document.body.appendChild(other);
    other.focus();
    mount({ focusOnOpen: "doc" });
    expect(document.activeElement).toBe(other);
    other.remove();
  });

  it("does not focus without the prop or while disabled", () => {
    mount();
    expect(document.activeElement).toBe(document.body);
    mount({ focusOnOpen: "doc", disabled: true });
    expect(document.activeElement).toBe(document.body);
  });
});

describe("Composer focusOnOpen keeps the user's focus", () => {
  function held() {
    const other = document.createElement("button");
    document.body.appendChild(other);
    other.focus();
    return other;
  }

  it("does not steal focus on a re-render with the same props", () => {
    const { rerender } = mount({ focusOnOpen: "doc" });
    const other = held();
    rerender(<Composer value="" onChange={() => {}} onSubmit={() => {}} focusOnOpen="doc" />);
    expect(document.activeElement).toBe(other);
    other.remove();
  });

  it("does not steal focus when disabled turns false while another control holds it", () => {
    const { rerender } = mount({ focusOnOpen: "doc", disabled: true });
    const other = held();
    rerender(<Composer value="" onChange={() => {}} onSubmit={() => {}} focusOnOpen="doc" disabled={false} />);
    expect(document.activeElement).toBe(other);
    other.remove();
  });

  it("focuses a remount for another profile only when nothing holds focus", () => {
    const first = mount({ focusOnOpen: "doc" });
    first.unmount();
    expect(document.activeElement).toBe(document.body);
    const second = mount({ focusOnOpen: "scout" });
    expect(document.activeElement).toBe(screen.getByRole("textbox"));
    second.unmount();
    const other = held();
    mount({ focusOnOpen: "pixel" });
    expect(document.activeElement).toBe(other);
    other.remove();
  });
});
