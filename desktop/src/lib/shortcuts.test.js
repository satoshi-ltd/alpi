import { describe, expect, it } from "vitest";
import { SHORTCUTS, keyTokens, shortcutKeys } from "./shortcuts.js";

describe("keyTokens", () => {
  it("splits modifiers from the key and keeps ranges whole", () => {
    expect(keyTokens("⌘1–9")).toEqual(["⌘", "1–9"]);
    expect(keyTokens("⇧⌘H")).toEqual(["⇧", "⌘", "H"]);
    expect(keyTokens("⌘,")).toEqual(["⌘", ","]);
    expect(keyTokens("⌘↵")).toEqual(["⌘", "↵"]);
    expect(keyTokens("Esc")).toEqual(["Esc"]);
  });

  it("treats prose hints as text, not keys", () => {
    expect(keyTokens("light · dark · system")).toBeNull();
    expect(keyTokens("")).toBeNull();
    expect(keyTokens(undefined)).toBeNull();
  });
});

describe("shortcut registry", () => {
  it("binds each key combination once", () => {
    const seen = SHORTCUTS.map((s) => s.keys);
    expect(new Set(seen).size).toBe(seen.length);
  });

  it("keeps ⌘N and ⇧⌘N distinct and exposes the new entries", () => {
    expect(shortcutKeys("new-session")).toBe("⌘N");
    expect(shortcutKeys("new-profile")).toBe("⇧⌘N");
    expect(shortcutKeys("shortcuts")).toBe("⌘/");
    expect(shortcutKeys("activity")).toBe("⌘J");
    expect(shortcutKeys("missing")).toBeNull();
  });

  it("renders every entry as key chips", () => {
    expect(SHORTCUTS.filter((s) => !keyTokens(s.keys)).map((s) => s.id)).toEqual([]);
  });
});
