import { describe, it, expect, vi } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { render } from "@testing-library/react";
import ChatHeader from "./ChatHeader.jsx";
import { nameTone } from "../../../common/name.mjs";
import { palettes } from "../../../common/tokens.mjs";

const titleGlyph = (container) => container.querySelector(".title-row").firstElementChild;

describe("ChatHeader", () => {
  it("draws the profile's mark at header size in its colour", () => {
    const { container } = render(<ChatHeader id="doc" accent="#3899e2" shape="drop" />);
    const glyph = titleGlyph(container);
    expect(glyph.dataset.shape).toBe("drop");
    expect(glyph.dataset.mark).toBe("drop");
    expect(glyph.style.width).toBe("28px");
    expect(glyph.querySelector("path[data-body]").getAttribute("fill")).toBe("#3899e2");
  });

  it("draws the round shape for a profile that never chose a fold", () => {
    const { container } = render(<ChatHeader id="doc" accent="#3899e2" />);
    expect(container.querySelector("[data-shape='round']").dataset.mark).toBe("round");
  });

  it.each(["idle", "working", "needs", "done", "failed"])("draws the session state %s on the animated header mark, which never follows the pointer", (state) => {
    const add = vi.spyOn(window, "addEventListener");
    const { container } = render(<ChatHeader id="doc" accent="#3899e2" shape="drop" state={state} />);
    const glyph = titleGlyph(container);
    expect(glyph.dataset.state).toBe(state);
    expect(glyph.hasAttribute("data-watch")).toBe(false);
    expect(add.mock.calls.filter(([type]) => type === "mousemove")).toHaveLength(0);
    add.mockRestore();
    if (state !== "idle") expect(glyph.querySelectorAll("animate").length).toBeGreaterThan(0);
  });

  it("draws paused over any session state, and idle when none is given", () => {
    const { container, rerender } = render(<ChatHeader id="doc" accent="#3899e2" shape="drop" state="working" paused />);
    expect(titleGlyph(container).dataset.state).toBe("paused");
    rerender(<ChatHeader id="doc" accent="#3899e2" shape="drop" />);
    expect(titleGlyph(container).dataset.state).toBe("idle");
  });

  it("sets a profile's name in the name face, a step darker in light and lighter in dark", () => {
    const { container } = render(<ChatHeader id="doc" accent="#3899e2" shape="drop" />);
    const name = container.querySelector("h1");
    expect(name.textContent).toBe("doc");
    expect(name.className).toBe("ds-name");
    expect(name.style.getPropertyValue("--name-light")).toBe(nameTone("#3899e2", palettes.light.bgPane));
    expect(name.style.getPropertyValue("--name-dark")).toBe(nameTone("#3899e2", palettes.dark.bgPane));
  });

  it("sets a workgroup's name in the name face in neutral ink, never the hub's tone", () => {
    const { container } = render(<ChatHeader kind="workgroup" id="ops" accent="#3899e2" />);
    const name = container.querySelector("h1");
    expect(name.className).toBe("ds-name");
    expect(name.style.getPropertyValue("--name-light")).toBe("");
    expect(name.style.getPropertyValue("--name-dark")).toBe("");
  });

  it("draws a workgroup as the neutral soft honeycomb at header size, dashed when paused", () => {
    const { container, rerender } = render(<ChatHeader kind="workgroup" id="ops" accent="#3899e2" />);
    const glyph = titleGlyph(container);
    expect(glyph.dataset.shape).toBe("honeycomb");
    expect(glyph.dataset.mark).toBe("soft-honeycomb");
    expect(glyph.style.width).toBe("28px");
    expect([...glyph.querySelectorAll("[data-cell]")].map((c) => c.getAttribute("fill"))).toEqual(["var(--ink-3)", "var(--ink-3)", "var(--ink-3)"]);
    rerender(<ChatHeader kind="workgroup" id="ops" accent="#3899e2" paused mark={{ state: "running", phase: [0, 2] }} />);
    expect(titleGlyph(container).dataset.state).toBe("paused");
    expect(container.querySelector("[data-cell] path").getAttribute("fill")).toBe("none");
  });

  it("passes the pipeline's phase to the workgroup mark and lights the cell in the hub's colour", () => {
    const { container } = render(<ChatHeader kind="workgroup" id="ops" accent="#3899e2" mark={{ state: "running", phase: [2, 3], owner: "lingo" }} />);
    const glyph = titleGlyph(container);
    expect(glyph.dataset.state).toBe("running");
    expect(glyph.dataset.cell).toBe("right");
    expect(glyph.querySelector("[data-lead]").getAttribute("fill")).toBe("var(--wg-lit)");
    expect(glyph.style.getPropertyValue("--wg-lit-light")).toBe(nameTone("#3899e2", palettes.light.bgPane));
  });
});

describe("ChatHeader paused", () => {
  it("draws a paused profile as its dashed grey outline", () => {
    const { container, rerender } = render(<ChatHeader kind="profile" id="doc" accent="#f36a8a" shape="heart" />);
    const live = container.querySelector("h1").getAttribute("style");
    rerender(<ChatHeader kind="profile" id="doc" accent="#f36a8a" shape="heart" paused />);
    const glyph = container.querySelector("[data-shape]");
    expect(glyph.dataset.state).toBe("paused");
    expect(glyph.querySelector("path[stroke-dasharray]").getAttribute("stroke")).toBe("var(--ink-3)");
    expect(live).toBeTruthy();
  });

  it("draws a paused name in ink-3 in both themes", () => {
    const { container, rerender } = render(<ChatHeader kind="profile" id="doc" accent="#f36a8a" shape="heart" />);
    expect(container.querySelector("h1").getAttribute("style")).not.toMatch(/ink-3/);
    rerender(<ChatHeader kind="profile" id="doc" accent="#f36a8a" shape="heart" paused />);
    expect(container.querySelector("h1").style.getPropertyValue("--name-light")).toBe("var(--ink-3)");
    expect(container.querySelector("h1").style.getPropertyValue("--name-dark")).toBe("var(--ink-3)");
  });
});

describe("ChatHeader bar type", () => {
  it("sets the name at the 20 px title size inside the bar, over the 28 px display rule", () => {
    const css = readFileSync(join(import.meta.dirname, "ChatHeader.module.css"), "utf8");
    expect(css).toMatch(/:global\(\.ds-chat-header\)\.bar h1 \{\s*font-size: var\(--text-title\);/);
    expect(css).toMatch(/\.label \{[^}]*font-size: var\(--text-title\);[^}]*font-weight: var\(--fw-regular\);[^}]*color: var\(--ink-3\);/);
  });

  it("keeps the name outside the menu button and names the button by it", () => {
    const { container } = render(<ChatHeader id="doc" accent="#3899e2" meta={<span>m</span>} />);
    const button = container.querySelector("button[aria-haspopup]");
    const h1 = container.querySelector("h1");
    expect(button.contains(h1)).toBe(false);
    expect(button.getAttribute("aria-labelledby")).toContain(h1.id);
  });

  it("draws a passive flag beside the name only when given one", () => {
    const { container, rerender } = render(<ChatHeader id="doc" accent="#3899e2" />);
    expect(container.querySelector("[data-flag]")).toBeNull();
    rerender(<ChatHeader id="doc" accent="#3899e2" flag={{ label: "Context 90% full" }} />);
    const flag = container.querySelector("[data-flag]");
    expect(flag).toHaveAttribute("aria-label", "Context 90% full");
    expect(flag.tagName).toBe("SPAN");
  });
});
