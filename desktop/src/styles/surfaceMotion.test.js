import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const read = (f) => readFileSync(join(import.meta.dirname, "..", f), "utf8");
const ds = read("styles/design-system.css");
const modal = read("primitives/Modal.module.css");

const frames = (css, name) => css.match(new RegExp(`@keyframes ${name}\\s*\\{([\\s\\S]*?\\})\\s*\\}`))?.[1] ?? "";
const travel = (body) => Number(body.match(/translateY\((?:var\(--menu-dy, )?(-?\d+)px/)?.[1] ?? 0);

describe("surface motion", () => {
  it("dialogs rise 8 px and settle from 0.98 on the enter curve", () => {
    expect(frames(ds, "ds-dialog-in")).toMatch(/from \{[^}]*translateY\(8px\) scale\(0\.98\)/);
    expect(ds).toMatch(/\.anim-dialog\s*\{ animation: ds-dialog-in var\(--dur-enter\) var\(--ease-enter\) both/);
  });

  it("menus grow from their anchor on fast, and leave on exit with no travel", () => {
    expect(frames(ds, "ds-menu-in")).toMatch(/translateY\(var\(--menu-dy, -4px\)\) scale\(0\.98\)/);
    expect(ds).toMatch(/\.anim-menu\s*\{ animation: ds-menu-in var\(--dur-fast\) var\(--ease-enter\) both/);
    expect(ds).toMatch(/\.anim-menu-out\s*\{ animation: ds-menu-out var\(--dur-exit\) var\(--ease-exit\) both; pointer-events: none/);
    expect(travel(frames(ds, "ds-menu-out"))).toBe(0);
  });

  it("toasts rise 8 px in and sink 4 px out", () => {
    expect(travel(frames(ds, "ds-notif-in"))).toBe(8);
    expect(travel(frames(ds, "ds-notif-out"))).toBe(4);
  });

  it("every exit travels less than its entrance", () => {
    expect(travel(frames(modal, "modalOut"))).toBe(4);
    expect(travel(frames(modal, "modalOut"))).toBeLessThan(travel(frames(ds, "ds-dialog-in")));
    expect(modal).toMatch(/\.modalClosing\s*\{\s*animation: modalOut var\(--dur-exit\) var\(--ease-exit\) both/);
  });

  it("introduces no duration or curve of its own", () => {
    const motion = [ds.match(/\.anim-(?:dialog|menu|menu-out)\s*\{[^}]*\}/g), modal.match(/\.modalClosing\s*\{[^}]*\}/)].flat().join("\n");
    expect(motion).not.toMatch(/\d+ms|cubic-bezier/);
  });

  it("stops under reduced motion through the global rule", () => {
    expect(ds).toMatch(/@media \(prefers-reduced-motion: reduce\)\s*\{\s*\*, \*::before, \*::after\s*\{\s*animation-duration: 0\.01ms !important/);
  });
});
