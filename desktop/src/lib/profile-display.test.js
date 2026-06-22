import { describe, expect, it } from "vitest";

import {
  DEFAULT_PROFILE_DISPLAY,
  PROFILE_NAME_RE,
  RESERVED_PROFILE_NAMES,
  isValidProfileName,
  profileLabel,
} from "./profile-display.js";

describe("RESERVED_PROFILE_NAMES", () => {
  it("mirrors the core contract (default + alpi)", () => {
    expect(RESERVED_PROFILE_NAMES).toEqual(["default", "alpi"]);
  });
});

describe("PROFILE_NAME_RE", () => {
  it.each(["work", "personal", "home-server", "build.debug", "a", "0", "a1", "a_b"])(
    "accepts %s",
    (name) => expect(PROFILE_NAME_RE.test(name)).toBe(true),
  );

  it.each(["", ".hidden", "-dash", "_under", "with space", "a/b", "..", "../escape"])(
    "rejects %s",
    (name) => expect(PROFILE_NAME_RE.test(name)).toBe(false),
  );
});

describe("isValidProfileName", () => {
  it.each(["work", "build.debug", "a.b.c", "a", "0", "x_y-z"])(
    "accepts %s",
    (name) => expect(isValidProfileName(name)).toBe(true),
  );

  it.each([
    "foo..bar",
    "a..b",
    "..",
    "...",
    "a..",
    "..b",
    ".hidden",
    "a/b",
    "",
    "with space",
  ])("rejects %s (path-traversal vector)", (name) =>
    expect(isValidProfileName(name)).toBe(false),
  );

  it("rejects non-strings", () => {
    expect(isValidProfileName(undefined)).toBe(false);
    expect(isValidProfileName(null)).toBe(false);
    expect(isValidProfileName(42)).toBe(false);
  });
});

describe("profileLabel", () => {
  it("maps default to the visual alias", () => {
    expect(profileLabel("default")).toBe(DEFAULT_PROFILE_DISPLAY);
  });

  it("returns named profiles as-is", () => {
    expect(profileLabel("work")).toBe("work");
  });
});
