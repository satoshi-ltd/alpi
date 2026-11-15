import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import AddMemberPopover from "./AddMemberPopover.jsx";
import CommandPalette from "../features/CommandPalette.jsx";

const shapes = (root) => [...root.querySelectorAll("[data-shape]")].map((el) => el.dataset.shape);

describe("fold carriers", () => {
  it("AddMemberPopover draws each candidate's own fold", () => {
    render(
      <AddMemberPopover
        open
        onClose={vi.fn()}
        candidates={[
          { id: "doc", accent: "#3899e2", shape: "arch", pubkey: "abcdef" },
          { id: "mind", accent: "#e2a038", pubkey: "ghijkl" },
        ]}
      />,
    );
    const [doc, mind] = screen.getAllByRole("button");
    expect(shapes(doc)).toEqual(["arch"]);
    expect(shapes(mind)).toEqual(["round"]);
  });

  it("CommandPalette draws a profile's fold in its search results", () => {
    render(
      <CommandPalette
        open
        onClose={vi.fn()}
        commands={[]}
        profiles={[{ name: "alpi", accent: "#f0b447", shape: "cloud" }]}
        onOpenProfile={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "alp" } });
    const option = screen.getAllByRole("option")[0];
    expect(shapes(option)).toEqual(["cloud"]);
  });
});
