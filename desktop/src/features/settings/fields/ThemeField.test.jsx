import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { ThemeField } from "./ThemeField.jsx";
import { cycleTheme, getTheme, setTheme } from "../../../lib/theme.js";

beforeEach(() => {
  localStorage.clear();
  setTheme("system");
});

describe("ThemeField", () => {
  it("renders System, Light and Dark with the stored one pressed", () => {
    render(<ThemeField />);
    expect(screen.getAllByRole("button").map((b) => b.textContent)).toEqual(["System", "Light", "Dark"]);
    expect(screen.getByRole("button", { name: "System" })).toHaveAttribute("aria-pressed", "true");
  });

  it("persists and applies the selected theme", () => {
    render(<ThemeField />);
    fireEvent.click(screen.getByRole("button", { name: "Dark" }));
    expect(getTheme()).toBe("dark");
    expect(document.documentElement.getAttribute("data-mode")).toBe("dark");
    expect(screen.getByRole("button", { name: "Dark" })).toHaveAttribute("aria-pressed", "true");
  });

  it("follows a palette cycle", () => {
    render(<ThemeField />);
    act(() => { cycleTheme(); });
    expect(screen.getByRole("button", { name: "Light" })).toHaveAttribute("aria-pressed", "true");
  });
});
