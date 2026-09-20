import { createRef } from "react";
import { buttonVariants } from "../../../common/button.mjs";
import { buttonStateCases } from "../../../common/button.fixtures.mjs";
import styles from "./Button.module.css";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Button from "./Button.jsx";

describe("Button loading", () => {
  it("keeps its label, announces busy state and prevents duplicate submissions", () => {
    const save = vi.fn();
    const { rerender } = render(<Button loading onClick={save}>Save</Button>);
    const button = screen.getByRole("button", { name: "Save" });
    expect(button).toHaveAttribute("aria-busy", "true");
    fireEvent.click(button);
    expect(save).not.toHaveBeenCalled();
    rerender(<Button onClick={save}>Save</Button>);
    expect(button).not.toHaveAttribute("aria-busy");
    fireEvent.click(button);
    expect(save).toHaveBeenCalledTimes(1);
  });
});

describe("Button contract", () => {
  it.each(buttonStateCases)("respects disabled=$disabled loading=$loading", ({ disabled, loading, blocked }) => {
    const press = vi.fn();
    render(<Button disabled={disabled} loading={loading} onClick={press}>Continue</Button>);
    const button = screen.getByRole("button", { name: "Continue" });
    expect(button.disabled).toBe(blocked);
    expect(button.getAttribute("aria-busy") === "true").toBe(loading);
    fireEvent.click(button);
    expect(press).toHaveBeenCalledTimes(blocked ? 0 : 1);
  });

  it.each(buttonVariants)("renders the %s variant", (variant) => {
    render(<Button variant={variant}>Continue</Button>);
    expect(screen.getByRole("button").className).toContain(styles[variant]);
    expect(styles[variant]).toBeTruthy();
  });

  it("forwards refs, native attributes and keyboard handlers to the button", () => {
    const ref = createRef();
    const key = vi.fn();
    render(<Button ref={ref} aria-expanded name="action" value="save" onKeyDown={key}>Save</Button>);
    const button = screen.getByRole("button", { name: "Save" });
    expect(ref.current).toBe(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(button).toHaveAttribute("name", "action");
    ref.current.focus();
    expect(document.activeElement).toBe(button);
    fireEvent.keyDown(button, { key: "Enter" });
    expect(key).toHaveBeenCalledTimes(1);
  });

  it("does not submit forms unless explicitly requested", () => {
    const submit = vi.fn((event) => event.preventDefault());
    render(<form onSubmit={submit}><Button>Cancel</Button><Button type="submit">Save</Button></form>);
    fireEvent.click(screen.getByText("Cancel"));
    expect(submit).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Save"));
    expect(submit).toHaveBeenCalledTimes(1);
  });

  it("keeps an icon-only button named during loading", () => {
    render(<Button icon={<span />} loading title="Refresh" aria-label="Refresh profiles" />);
    expect(screen.getByRole("button", { name: "Refresh profiles" })).toBeDisabled();
  });

  it("supports full width without adding layout styles to callers", () => {
    render(<Button fullWidth>Continue</Button>);
    expect(screen.getByRole("button")).toHaveClass(styles.fullWidth);
  });
});
