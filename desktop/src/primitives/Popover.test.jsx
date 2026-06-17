import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { useState } from "react";

import Popover from "./Popover.jsx";

function Harness() {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <span style={{ position: "relative" }}>
        <button onClick={() => setOpen((o) => !o)}>trigger</button>
        <Popover open={open} onClose={() => setOpen(false)}>
          <div>panel</div>
        </Popover>
      </span>
    </div>
  );
}

describe("Popover", () => {
  it("clicking the open trigger closes it (does not re-open)", () => {
    render(<Harness />);
    fireEvent.click(screen.getByText("trigger"));
    expect(screen.getByText("panel")).toBeTruthy();
    // A real click = mousedown (the outside-close listener) + click (the trigger's toggle).
    fireEvent.mouseDown(screen.getByText("trigger"));
    fireEvent.click(screen.getByText("trigger"));
    expect(screen.queryByText("panel")).toBeNull();
  });

  it("clicking outside the wrapper closes it", () => {
    render(<Harness />);
    fireEvent.click(screen.getByText("trigger"));
    expect(screen.getByText("panel")).toBeTruthy();
    fireEvent.mouseDown(document.body);
    expect(screen.queryByText("panel")).toBeNull();
  });
});
