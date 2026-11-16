import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";

vi.mock("../lib/useAttention.js", () => ({ useAttention: () => ({}) }));
vi.mock("./SkillsModal.jsx", () => ({ SkillsPanel: () => <p>skills body</p> }));
vi.mock("./ToolsModal.jsx", () => ({ ToolsPanel: () => <p>tools body</p> }));
vi.mock("./ScheduleModal.jsx", () => ({ SchedulePanel: () => <p>schedule body</p> }));
vi.mock("./MemoryModal.jsx", () => ({ MemoryPanel: () => <p>memory body</p> }));

import ProfilePanels from "./ProfilePanels.jsx";

beforeEach(() => {
  vi.useFakeTimers();
  window.matchMedia = vi.fn(() => ({ matches: false, addEventListener() {}, removeEventListener() {} }));
});
afterEach(() => {
  vi.useRealTimers();
  delete window.matchMedia;
});

describe("ProfilePanels exit", () => {
  it("keeps the section and its label on screen while the window leaves", () => {
    const { rerender } = render(<ProfilePanels section="skills" profile="doc" onClose={() => {}} />);
    expect(screen.getByText("skills body")).toBeInTheDocument();
    rerender(<ProfilePanels section={null} profile="doc" onClose={() => {}} />);
    expect(screen.getByText("skills body")).toBeInTheDocument();
    expect(screen.getByRole("dialog", { hidden: true })).toHaveAttribute("aria-label", expect.stringContaining("Skills"));
    expect(screen.getByRole("dialog", { hidden: true })).toHaveClass("anim-dialog-out");
    act(() => vi.advanceTimersByTime(200));
    expect(screen.queryByText("skills body")).toBeNull();
  });
});
