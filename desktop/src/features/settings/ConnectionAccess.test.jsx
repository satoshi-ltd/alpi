import { readFileSync } from "node:fs";
import { join } from "node:path";
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConnectionAccess } from "./ConnectionsPage.jsx";
import { nameTone } from "../../../../common/name.mjs";
import { palettes } from "../../../../common/tokens.mjs";

const PROFILES = [
  { name: "doc", accent: "#3899e2", shape: "squircle" },
  { name: "lingo", accent: "#9b5ad9", shape: "clover" },
  { name: "abby", accent: "#df4b9d", shape: "drop" },
  { name: "yuri", accent: "#f36a8a", shape: "heart" },
  { name: "galt", accent: "#6572e4", shape: "arch" },
];

const access = (row) => render(<ConnectionAccess row={row} profiles={PROFILES} />).container.firstElementChild;

describe("ConnectionAccess", () => {
  it("reads All profiles for an admin and for a member with no scope", () => {
    expect(access({ role: "admin", profile_scope: ["doc"] }).textContent).toBe("All profiles");
    expect(access({ role: "member", profile_scope: [] }).textContent).toBe("All profiles");
  });

  it("draws each profile in scope as its mark and its name in its own tone", () => {
    const el = access({ role: "member", profile_scope: ["lingo"] });
    const profile = el.firstElementChild;
    expect(profile.querySelector("[data-shape='clover']")).not.toBeNull();
    expect(profile.textContent).toBe("lingo");
    expect(profile.style.getPropertyValue("--name-light")).toBe(nameTone("#9b5ad9", palettes.light.bgPane));
    expect(el.getAttribute("aria-label")).toBe("lingo");
  });

  it("shows the first three then +N with the rest in the tooltip and every name in the accessible name", () => {
    const el = access({ role: "member", profile_scope: ["doc", "lingo", "abby", "yuri", "galt"] });
    expect(el.querySelectorAll("[data-shape]")).toHaveLength(3);
    const more = el.lastElementChild;
    expect(more.textContent).toBe("+2");
    expect(more.getAttribute("title")).toBe("yuri, galt");
    expect(el.getAttribute("aria-label")).toBe("doc, lingo, abby, yuri, galt");
  });

  it("strikes a profile the roster no longer has, with no mark, and says so to a screen reader", () => {
    const el = access({ role: "member", profile_scope: ["doc", "archive"] });
    const gone = [...el.children].find((child) => child.textContent === "archive");
    expect(gone.querySelector("[data-shape]")).toBeNull();
    expect(gone.getAttribute("title")).toBe("No longer on this daemon");
    expect(el.getAttribute("role")).toBe("group");
    expect(el.getAttribute("aria-label")).toBe("doc, archive (removed)");
  });

  it("names the scope plainly, struck nowhere, until the roster has loaded", () => {
    const el = render(<ConnectionAccess row={{ role: "member", profile_scope: ["doc"] }} profiles={null} />).container.firstElementChild;
    expect(el.textContent).toBe("doc");
    expect(el.querySelector("[title]")).toBeNull();
    expect(el.getAttribute("aria-label")).toBe("doc");
  });

  it("tones the names for the card ground of an open row", () => {
    const el = render(<ConnectionAccess row={{ role: "member", profile_scope: ["lingo"] }} profiles={PROFILES} ground="card" />).container.firstElementChild;
    expect(el.firstElementChild.style.getPropertyValue("--name-light")).toBe(nameTone("#9b5ad9", palettes.light.card));
  });

  it("centres the table and the audit log on one column under a header that runs the pane", () => {
    const css = readFileSync(join(import.meta.dirname, "ConnectionsPage.module.css"), "utf8");
    expect(css).toMatch(/\.table \{[^}]*max-width: var\(--connections-col\);[^}]*margin-inline: auto/);
    expect(css).toMatch(/\.audit \{[^}]*max-width: var\(--connections-col\);[^}]*margin-inline: auto/);
    expect(css).not.toMatch(/header:global\(\.ds-chat-header\)/);
  });
});
