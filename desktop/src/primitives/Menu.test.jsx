import { fireEvent, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it, vi } from "vitest";

import ContextMenu from "./ContextMenu.jsx";
import Dropdown from "./Dropdown.jsx";
import HeaderMenu from "./HeaderMenu.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };

const css = readFileSync(join(import.meta.dirname, "Menu.module.css"), "utf8");

function openEffort(current = "medium") {
  render(
    <Dropdown trigger={{ label: "Effort" }}>
      {() => ["low", "medium", "high"].map((v) => (
        <Dropdown.Row key={v} active={v === current} caption={`${v} caption`}>{v}</Dropdown.Row>
      ))}
    </Dropdown>,
  );
  fireEvent.click(screen.getByRole("button", { name: /Effort/ }));
}

describe("menu roles", () => {
  it("labels a group and hides its eyebrow from the menu's children", () => {
    render(
      <Dropdown trigger={{ label: "Pick" }}>
        {() => (
          <Dropdown.Group label="Tier">
            <Dropdown.Row>one</Dropdown.Row>
            <Dropdown.Row active>two</Dropdown.Row>
          </Dropdown.Group>
        )}
      </Dropdown>,
    );
    fireEvent.click(screen.getByRole("button", { name: /Pick/ }));
    const group = screen.getByRole("group", { name: "Tier" });
    expect(screen.getByText("Tier")).toHaveAttribute("role", "presentation");
    expect(group.querySelectorAll('[role="menuitem"], [role="menuitemradio"]')).toHaveLength(2);
  });
});

describe("menu primitive", () => {
  it("sizes every row at 32 px with 8/12 padding and a 16 px check slot", () => {
    expect(css).toMatch(/\.row \{[^}]*min-height: var\(--ctl-32\);[^}]*padding: var\(--sp-8\) var\(--sp-12\);/);
    expect(css).toMatch(/\.check \{[^}]*width: var\(--icon-md\);/);
    expect(css).toMatch(/\.sepInset \{[^}]*margin-left: calc\(var\(--sp-12\) \+ var\(--icon-md\) \+ var\(--sp-8\)\);/);
  });

  it("marks a dropdown choice with a check, weight and aria-checked, not tint alone", () => {
    openEffort();
    expect(screen.getByRole("menu")).toBeInTheDocument();
    const items = screen.getAllByRole("menuitemradio");
    expect(items.map((el) => el.getAttribute("aria-checked"))).toEqual(["false", "true", "false"]);
    expect(items[1].querySelector("svg")).not.toBeNull();
    expect(items[0].querySelector("svg")).toBeNull();
    expect(items[0].querySelector('[aria-hidden="true"]')).not.toBeNull();
    expect(items[1].className).toMatch(/rowSelected/);
  });

  it("declares the trigger as a menu popup and keeps arrow navigation", () => {
    openEffort();
    expect(screen.getByRole("button", { name: /Effort/ })).toHaveAttribute("aria-haspopup", "menu");
    const items = screen.getAllByRole("menuitemradio");
    items[0].focus();
    fireEvent.keyDown(items[0], { key: "ArrowDown" });
    expect(document.activeElement).toBe(items[1]);
  });

  it("gives action rows the menuitem role with no check slot", () => {
    render(
      <Dropdown trigger={{ label: "Actions" }}>
        {() => <Dropdown.Row>Rename</Dropdown.Row>}
      </Dropdown>,
    );
    fireEvent.click(screen.getByRole("button", { name: /Actions/ }));
    const row = screen.getByRole("menuitem", { name: "Rename" });
    expect(row).not.toHaveAttribute("aria-checked");
    expect(row.querySelector("svg")).toBeNull();
  });

  it("renders context menu rows, separators and danger rows on the shared rows", () => {
    const onClick = vi.fn();
    render(
      <ContextMenu
        x={10}
        y={10}
        onClose={() => {}}
        items={[
          { label: "Rename", onClick },
          { kind: "separator" },
          { label: "Delete", kind: "danger" },
        ]}
      />,
    );
    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(screen.getAllByRole("menuitem")).toHaveLength(2);
    expect(screen.getByRole("separator")).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Rename" }).className).toMatch(/row/);
    expect(screen.getByRole("menuitem", { name: "Delete" }).className).toMatch(/danger/);
  });

  it("opens the header menu from a menu-popup trigger with menuitem rows and a checkbox toggle", () => {
    render(<HeaderMenu onOpenSettings={() => {}} onToggleAutoRead={() => {}} autoRead onOpenSkills={() => {}} />);
    const trigger = screen.getByRole("button", { name: "More" });
    expect(trigger).toHaveAttribute("aria-haspopup", "menu");
    fireEvent.click(trigger);
    expect(screen.getByRole("menuitem", { name: /Profile settings/ }).className).toMatch(/row/);
    expect(screen.getByRole("menuitemcheckbox", { name: /Auto-read replies/ })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("separator")).toBeInTheDocument();
  });
});
