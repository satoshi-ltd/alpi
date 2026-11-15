import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import SettingsHero from "./SettingsHero.jsx";
import { nameTone } from "../../../common/name.mjs";
import { palettes } from "../../../common/tokens.mjs";

describe("SettingsHero", () => {
  it("sets a profile's name in the name face, in the accent's ink tone", () => {
    const { container } = render(<SettingsHero id="doc" accent="#3899e2" shape="drop" />);
    const h1 = container.querySelector("h1");
    expect(h1.className).toBe("ds-name");
    expect(h1.style.getPropertyValue("--name-light")).toMatch(/^#[0-9a-f]{6}$/);
  });

  it("sets a workgroup's name in the name face in neutral ink, muted when paused", () => {
    const { container, rerender } = render(<SettingsHero kind="workgroup" id="ops" accent="#3899e2" />);
    const h1 = container.querySelector("h1");
    expect(h1.className).toBe("ds-name");
    expect(h1.style.getPropertyValue("--name-light")).toBe("");
    rerender(<SettingsHero kind="workgroup" id="ops" accent="#3899e2" paused />);
    expect(container.querySelector("h1").style.getPropertyValue("--name-light")).toBe("var(--ink-3)");
  });

  it("sets the connections heading in the name face too", () => {
    const { container } = render(<SettingsHero kind="connections" id="alpi" accent="#3899e2" />);
    const h1 = container.querySelector("h1");
    expect(h1.textContent).toBe("alpi");
    expect(h1.className).toBe("ds-name");
  });

  it("draws a workgroup as the neutral soft honeycomb at header size, dashed and frontal when paused", () => {
    const { container, rerender } = render(<SettingsHero kind="workgroup" id="ops" accent="#3899e2" />);
    const glyph = container.querySelector(".title-row").firstElementChild;
    expect(glyph.dataset.shape).toBe("honeycomb");
    expect(glyph.dataset.mark).toBe("soft-honeycomb");
    expect(glyph.style.width).toBe("28px");
    expect([...glyph.querySelectorAll("path")].map((p) => p.getAttribute("fill"))).toEqual(["var(--ink-3)", "var(--ink-3)", "var(--ink-3)"]);
    rerender(<SettingsHero kind="workgroup" id="ops" accent="#3899e2" paused mark={{ state: "running", phase: [1, 3] }} />);
    const paused = container.querySelector(".title-row").firstElementChild;
    expect(paused.dataset.state).toBe("paused");
    expect([...paused.querySelectorAll("path")].every((p) => p.getAttribute("fill") === "none" && p.getAttribute("stroke-dasharray"))).toBe(true);
    expect(paused.querySelector("svg").style.transform).toBe("rotateY(0deg) rotateX(0deg) rotateZ(0deg)");
  });

  it("leans the workgroup's active cell in the hub's colour, never the phase owner's", () => {
    const { container } = render(<SettingsHero kind="workgroup" id="ops" accent="#3899e2" mark={{ state: "running", phase: [1, 3], owner: "lingo", active: "#f36a8a" }} />);
    const glyph = container.querySelector(".title-row").firstElementChild;
    expect(glyph.dataset.cell).toBe("top");
    expect(glyph.querySelector('[data-lead]').getAttribute("fill")).toBe("var(--wg-lit)");
    expect(glyph.style.getPropertyValue("--wg-lit-dark")).toBe(nameTone("#3899e2", palettes.dark.bgPane));
    expect(glyph.innerHTML).not.toContain("#f36a8a");
  });

  it.each([["profile", "Settings"], ["workgroup", "Settings"], ["connections", "Connections"]])("ships the 56 px chat bar for %s with the sentence-case label and no eyebrow", (kind, label) => {
    const onOpenChat = vi.fn();
    const { container } = render(<SettingsHero kind={kind} id="doc" accent="#3899e2" shape="drop" meta={<span>gpt</span>} onOpenChat={onOpenChat} />);
    const header = container.querySelector("header");
    expect(header.className).toMatch(/ds-chat-header/);
    expect(container.querySelector(".eyebrow")).toBeNull();
    expect(container.querySelector(".meta-row")).toBeNull();
    const row = container.querySelector(".title-row");
    expect(row.querySelector("h1").nextElementSibling.textContent).toBe(label);
    expect(screen.getByRole("button", { name: "doc details" })).toHaveAttribute("aria-haspopup", "dialog");
    fireEvent.click(screen.getByRole("button", { name: "Back to chat" }));
    expect(onOpenChat).toHaveBeenCalled();
  });
});
