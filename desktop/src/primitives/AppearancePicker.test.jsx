import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { FOLD_IDS } from "../../../common/folds.mjs";
import { ACCENTS } from "../../../common/accents.mjs";
import AppearancePicker from "./AppearancePicker.jsx";

afterEach(cleanup);

const open = (props = {}) => {
  const onChange = vi.fn();
  render(<AppearancePicker fold="shield" accent="#3899e2" onChange={onChange} {...props} />);
  fireEvent.click(screen.getByRole("button", { name: /shield/ }));
  return onChange;
};

describe("AppearancePicker", () => {
  it("names the pair on its trigger and stays closed until clicked", () => {
    const onChange = vi.fn();
    render(<AppearancePicker fold="shield" accent="#3899e2" onChange={onChange} />);
    expect(screen.getByRole("button", { name: "blue shield" })).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Reset to diamond")).toBeNull();
  });

  it("falls back to the amber diamond for a profile with neither", () => {
    render(<AppearancePicker onChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: "amber diamond" })).toBeInTheDocument();
  });

  it("offers the twelve objects and the twelve colours", () => {
    open();
    for (const id of FOLD_IDS) expect(screen.getByRole("button", { name: id })).toBeInTheDocument();
    for (const [name, hex] of ACCENTS) expect(screen.getByRole("button", { name: `${name} ${hex}` })).toBeInTheDocument();
    expect(FOLD_IDS).toHaveLength(12);
    expect(ACCENTS).toHaveLength(12);
  });

  it("marks the current object and colour as pressed, and nothing else", () => {
    open();
    const pressed = screen.getAllByRole("button", { pressed: true }).map((b) => b.getAttribute("aria-label"));
    expect(pressed.sort()).toEqual(["blue #3899e2", "shield"]);
  });

  it("marks the nearest swatch for a free-form accent", () => {
    open({ accent: "#3a9ae3" });
    expect(screen.getByRole("button", { name: "blue #3899e2" })).toHaveAttribute("aria-pressed", "true");
  });

  it("picking an object changes only the fold", () => {
    const onChange = open();
    fireEvent.click(screen.getByRole("button", { name: "heart" }));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith({ fold: "heart" });
  });

  it("picking a colour changes only the accent and mirrors it in the hex field", () => {
    const onChange = open();
    fireEvent.click(screen.getByRole("button", { name: "rose #f36a8a" }));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith({ accent: "#f36a8a" });
    expect(screen.getByPlaceholderText("#hex")).toHaveValue("#f36a8a");
  });

  it("resets the object to the diamond and leaves the colour alone", () => {
    const onChange = open();
    fireEvent.click(screen.getByRole("button", { name: "Reset to diamond" }));
    expect(onChange).toHaveBeenCalledWith({ fold: "diamond" });
    expect(onChange.mock.calls[0][0]).not.toHaveProperty("accent");
  });

  it("previews the pair by name with the values that will be saved", () => {
    open();
    expect(screen.getByText("Blue shield")).toBeInTheDocument();
    expect(screen.getByText('fold: shield · accent: "#3899e2"')).toBeInTheDocument();
  });

  it("commits a valid hex and explains an invalid one without committing it", () => {
    const onChange = open();
    const input = screen.getByPlaceholderText("#hex");
    fireEvent.change(input, { target: { value: "#12" } });
    expect(screen.getByText("must be 6-digit #hex")).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
    fireEvent.change(input, { target: { value: "#123abc" } });
    expect(screen.queryByText("must be 6-digit #hex")).toBeNull();
    expect(onChange).toHaveBeenCalledWith({ accent: "#123abc" });
  });

  it("closes on Escape", () => {
    open();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByText("Reset to diamond")).toBeNull();
  });

  it("lays the twelve colours out like the objects: a six-column grid of the same 42 px tiles", async () => {
    const { readFileSync } = await import("node:fs");
    const { join } = await import("node:path");
    const css = readFileSync(join(import.meta.dirname, "AppearancePicker.module.css"), "utf8");
    const block = (selector) => css.match(new RegExp(`${selector.replace(".", "\\.")}\\s*\\{([^}]*)\\}`))[1];
    expect(block(".colours")).toContain("repeat(6, 1fr)");
    expect(block(".objects")).toContain("repeat(6, 1fr)");
    expect(block(".colours .colour")).toContain("width: 42px");
    expect(block(".objects .object")).toContain("width: 42px");
  });
});
