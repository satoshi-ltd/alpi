import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import ModelPicker from "./ModelPicker.jsx";

const css = readFileSync(join(import.meta.dirname, "ModelPicker.module.css"), "utf8");
const MODELS = { a: [{ id: "a/x", label: "x" }, { id: "a/y", label: "y" }] };

function mount(props = {}) {
  return render(<ModelPicker currentModel="a/x" models={MODELS} onPick={() => {}} {...props} />);
}

describe("ModelPicker effort", () => {
  it("caps the label with an ellipsis on the model and never on the effort", () => {
    expect(css).toMatch(/\.modelPickerLabel\s*\{[^}]*max-width:\s*160px/);
    expect(css).toMatch(/\.modelPickerLabelModel\s*\{[^}]*text-overflow:\s*ellipsis/);
    expect(css).toMatch(/\.modelPickerLabelEffort\s*\{[^}]*flex:\s*none/);
  });

  it("appends the effort to the label only when the model supports it", () => {
    const { unmount } = mount({ effort: "high", effortSupported: true });
    expect(screen.getByRole("button")).toHaveTextContent("x · high");
    unmount();
    mount({ effort: "high", effortSupported: false });
    expect(screen.getByRole("button")).not.toHaveTextContent("high");
  });

  it("holds a segmented effort row that applies on pick and stays open", () => {
    const onEffortChange = vi.fn();
    mount({ effort: "", effortSupported: true, onEffortChange });
    fireEvent.click(screen.getByRole("button"));
    const group = screen.getByRole("radiogroup", { name: "Reasoning effort" });
    expect(group.querySelectorAll('[role="radio"]')).toHaveLength(4);
    expect(screen.getByRole("radio", { name: "Default" })).toHaveAttribute("aria-checked", "true");
    fireEvent.click(screen.getByRole("radio", { name: "Medium" }));
    expect(onEffortChange).toHaveBeenCalledWith("medium");
    expect(screen.getByRole("radiogroup")).toBeInTheDocument();
  });

  it("keeps the model options as listbox options and reaches the effort row by arrow keys", () => {
    mount({ effort: "", effortSupported: true });
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getAllByRole("option")).toHaveLength(2);
    const listbox = screen.getByRole("listbox");
    screen.getAllByRole("option")[1].focus();
    fireEvent.keyDown(screen.getAllByRole("option")[1], { key: "ArrowDown" });
    expect(document.activeElement).toBe(screen.getByRole("radio", { name: "Default" }));
    expect(listbox).toBeInTheDocument();
  });

  it("keeps the listbox to options and puts the effort row outside it", () => {
    mount({ effort: "", effortSupported: true });
    fireEvent.click(screen.getByRole("button"));
    const listbox = screen.getByRole("listbox");
    for (const child of listbox.querySelectorAll("*")) {
      expect(["option", "group", "presentation", null]).toContain(child.getAttribute("role") ?? (child.tagName === "BUTTON" ? "button" : null));
    }
    expect(listbox.querySelector('[role="radiogroup"]')).toBeNull();
    expect(screen.getByRole("radiogroup")).toBeInTheDocument();
    expect(screen.getByText("Reasoning effort · saved for this profile")).toBeInTheDocument();
  });

  it("gates the effort row on the model picked when given a per-model check", () => {
    mount({ effort: "low", effortSupported: (id) => id === "a/x" });
    expect(screen.getByRole("button")).toHaveTextContent("x · low");
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByRole("radiogroup")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("option", { name: /y/ }));
    expect(screen.getByRole("button")).not.toHaveTextContent("low");
    fireEvent.click(screen.getByRole("button"));
    expect(screen.queryByRole("radiogroup")).toBeNull();
  });

  it("shows no effort row without support", () => {
    mount();
    fireEvent.click(screen.getByRole("button"));
    expect(screen.queryByRole("radiogroup")).toBeNull();
  });
});
