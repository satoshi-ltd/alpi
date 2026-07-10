import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import CommandPalette from "./CommandPalette.jsx";

describe("CommandPalette", () => {
  it("keeps shortcut help rows informational", () => {
    const onClose = vi.fn();
    render(
      <CommandPalette
        open
        onClose={onClose}
        commands={[
          {
            id: "help:jump",
            group: "General",
            label: "Jump to profile / workgroup",
            hint: "⌘1–9",
          },
        ]}
      />,
    );

    fireEvent.click(screen.getByText("Jump to profile / workgroup"));

    expect(onClose).not.toHaveBeenCalled();
  });

  it("runs command rows and closes the palette", () => {
    const onClose = vi.fn();
    const action = vi.fn();
    render(
      <CommandPalette
        open
        onClose={onClose}
        commands={[
          {
            id: "view:notifications",
            group: "View",
            label: "Notifications",
            hint: "⌘O",
            action,
          },
        ]}
      />,
    );

    fireEvent.click(screen.getByText("Notifications"));

    expect(action).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
