import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fireEvent, render, screen, within } from "@testing-library/react";
import ProfileChatHeader from "./ProfileChatHeader.jsx";

const profile = { name: "doc", accent: "#3899e2", shape: "drop", model: "openrouter/deepseek/deepseek-v4.1-flash", budget_daily_usd: 1, budget_used_usd: 0.25 };

const mount = () =>
  render(<ProfileChatHeader profile={profile} sessionData={{ last_ctx_tokens: 20000 }} model={profile.model} contextWindow={200000} sessionsButton={null} />);

describe("ProfileChatHeader profile menu", () => {
  it("draws no meta line under the name: the header is the mark, the name and a chevron", () => {
    const { container } = mount();
    expect(container.querySelector(".meta-row")).toBeNull();
    const title = screen.getByRole("button", { name: "doc details" });
    expect(title.querySelector("h1")).toBeNull();
    const name = container.querySelector(".title-row > h1.ds-name");
    expect(name.textContent).toBe("doc");
    expect(title.getAttribute("aria-labelledby").split(" ")[0]).toBe(name.id);
    expect(title.querySelector("[data-icon]")).not.toBeNull();
    expect(title).toHaveAttribute("aria-haspopup", "dialog");
    expect(title).toHaveAttribute("aria-expanded", "false");
  });

  it("opens a profile menu holding the model, the context and the cost", () => {
    mount();
    const menu = document.querySelector("[role='dialog'][aria-label='doc details']");
    expect(menu.hidden).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "doc details" }));
    expect(menu.hidden).toBe(false);
    expect(screen.getByRole("button", { name: "doc details" })).toHaveAttribute("aria-expanded", "true");
    const text = within(menu).getAllByText(/./).map((el) => el.textContent).join(" | ");
    expect(text).toMatch(/Model/);
    expect(text).toMatch(/deepseek-v4\.1-flash/);
    expect(text).toMatch(/Context/);
    expect(text).toMatch(/20K/);
    expect(text).toMatch(/Cost today/);
    expect(text).toMatch(/\$0\.25/);
  });

  it("closes the menu when the title is pressed again", () => {
    mount();
    const title = screen.getByRole("button", { name: "doc details" });
    fireEvent.click(title);
    fireEvent.click(title);
    expect(document.querySelector("[role='dialog'][aria-label='doc details']").hidden).toBe(true);
  });

  it("floats the menu on the raised surface and keeps the header 56 px with no line", () => {
    const css = readFileSync(join(import.meta.dirname, "ChatHeader.module.css"), "utf8");
    expect(css).toMatch(/\.menu \{[^}]*background: var\(--raised\);[^}]*box-shadow: var\(--shadow-float\);/);
    expect(css).toMatch(/\.menu \{[^}]*border-radius: var\(--r-surface\);/);
    expect(css).not.toMatch(/border-bottom|var\(--line/);
  });
});
