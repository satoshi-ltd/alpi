import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ShortcutsSheet, { groupShortcuts } from "./ShortcutsSheet.jsx";
import { SHORTCUTS } from "../lib/shortcuts.js";

describe("ShortcutsSheet", () => {
  it("lists every registry shortcut once, grouped", () => {
    render(<ShortcutsSheet open onClose={vi.fn()} />);
    const labels = Array.from(document.querySelectorAll("dt")).map((n) => n.textContent);
    expect(labels).toHaveLength(SHORTCUTS.length);
    expect(new Set(labels)).toEqual(new Set(SHORTCUTS.map((s) => s.label)));
    expect(screen.getByRole("region", { name: "Profile or workgroup" })).toBeInTheDocument();
    expect(groupShortcuts().flatMap(([, items]) => items)).toHaveLength(SHORTCUTS.length);
    expect(document.querySelector('[data-keys="⌘1–9"]').textContent).toBe("⌘1–9");
    expect(document.querySelectorAll('[data-keys="⌘1–9"] [aria-hidden]')).toHaveLength(2);
  });

  it("renders nothing while closed", () => {
    const { container } = render(<ShortcutsSheet open={false} onClose={vi.fn()} />);
    expect(container.innerHTML).toBe("");
  });
});
