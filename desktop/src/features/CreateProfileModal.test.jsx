import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn(async () => []) }));
vi.mock("../primitives/Notification.jsx", () => ({ useNotify: () => () => {} }));

import CreateProfileModal from "./CreateProfileModal.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };

const backdrop = () => document.querySelector('[role="dialog"]').parentElement;

describe("CreateProfileModal", () => {
  it("uses the shared Field for every text input", () => {
    render(<CreateProfileModal open onClose={() => {}} />);
    const inputs = document.querySelectorAll('[role="dialog"] input');
    expect(inputs.length).toBeGreaterThan(0);
    for (const input of inputs) expect(input).toHaveClass("ds-field");
  });

  it("closes on a backdrop click while pristine", () => {
    const onClose = vi.fn();
    render(<CreateProfileModal open onClose={onClose} />);
    fireEvent.mouseDown(backdrop());
    expect(onClose).toHaveBeenCalled();
  });

  it("ignores the backdrop once a name is typed, but Cancel still closes", () => {
    const onClose = vi.fn();
    render(<CreateProfileModal open onClose={onClose} />);
    fireEvent.change(screen.getByPlaceholderText(/work · personal/), { target: { value: "work" } });
    fireEvent.mouseDown(backdrop());
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalled();
  });
});
