import { describe, it, expect } from "vitest";
import {
  SIDEBAR_W,
  MIN_W,
  MIN_H,
  HYSTERESIS,
  BUBBLE_MAX_PANE,
  CONTENT_MAX_W,
  PANE_PAD_X,
  isTwoPane,
  nextTwoPane,
  isFullBleed,
  isHome,
  isPaneRoot,
  OUTPUTS_PATH,
  resumePath,
  SETTINGS_PATH,
  sidebarSelection,
  subjectPath,
  openVerb,
  stackAnimation,
} from "./panes.js";
import { space } from "../theme/tokens.js";

describe("constants", () => {
  it("pins the decided breakpoint", () => {
    expect(SIDEBAR_W).toBe(320);
    expect(MIN_W).toBe(700);
    expect(MIN_H).toBe(500);
    expect(HYSTERESIS).toBe(24);
  });
});

describe("content metrics", () => {
  it("keeps the pane edge on a token, never a raw pixel", () => {
    expect(Object.values(space)).toContain(PANE_PAD_X);
    expect(CONTENT_MAX_W).toBe(720);
  });

  it("mirrors desktop --bubble-max", () => {
    expect(BUBBLE_MAX_PANE).toBe("76%");
  });

  it("exposes one edge, not a per-surface gutter", async () => {
    const panes = await import("./panes.js");
    expect(Object.keys(panes).filter((k) => /GUTTER|PAD_X/.test(k))).toEqual(["PANE_PAD_X"]);
    expect(panes.headerGutter).toBeUndefined();
  });
});

describe("stackAnimation", () => {
  it("kills the slide in two-pane mode", () => {
    expect(stackAnimation(true)).toBe("none");
  });

  it("keeps the slide on one pane", () => {
    expect(stackAnimation(false)).toBe("slide_from_right");
  });
});

describe("isTwoPane", () => {
  it.each([
    ["iPhone 17 Pro Max portrait", 440, 956, false],
    ["iPhone 17 Pro Max landscape", 956, 440, false],
    ["iPad Slide Over over a portrait host", 320, 1194, false],
    ["iPad Slide Over over a landscape host", 320, 834, false],
    ["iPad Split View 1/2", 507, 1194, false],
    ["iPad Split View 2/3", 686, 1194, false],
    ["iPad mini portrait", 744, 1133, true],
    ["iPad mini landscape", 1133, 744, true],
    ['iPad 11" portrait', 834, 1194, true],
    ['iPad 11" landscape', 1194, 834, true],
    ["Pixel 9 Pro Fold unfolded portrait", 852, 883, true],
    ["Pixel 9 Pro Fold unfolded landscape", 883, 852, true],
    ["Pixel 9 Pro Fold cover portrait", 443, 995, false],
    ["Pixel 9 Pro Fold cover landscape", 995, 443, false],
    ['Android 10" tablet portrait', 800, 1280, true],
    ['Android 10" tablet landscape', 1280, 800, true],
  ])("%s %ix%i → %s panes", (_name, width, height, expected) => {
    expect(isTwoPane(width, height)).toBe(expected);
  });

  it.each([
    [700, 500, true],
    [699, 500, false],
    [700, 499, false],
    [1194, 499, false],
  ])("%ix%i → %s at the exact threshold", (width, height, expected) => {
    expect(isTwoPane(width, height)).toBe(expected);
  });
});

describe("nextTwoPane", () => {
  it("needs the full width to enter two panes", () => {
    expect(nextTwoPane(false, 699, 1194)).toBe(false);
    expect(nextTwoPane(false, 700, 1194)).toBe(true);
  });

  it("holds two panes down to HYSTERESIS below the threshold", () => {
    expect(nextTwoPane(true, 690, 1194)).toBe(true);
    expect(nextTwoPane(true, 676, 1194)).toBe(true);
    expect(nextTwoPane(true, 675, 1194)).toBe(false);
  });

  it("drops to one pane whenever the height gate fails, whatever prev says", () => {
    expect(nextTwoPane(true, 1194, 499)).toBe(false);
    expect(nextTwoPane(false, 1194, 499)).toBe(false);
    expect(nextTwoPane(true, 956, 440)).toBe(false);
  });

  it("does not thrash across a Split View divider drag", () => {
    const widths = [690, 700, 690, 680, 676, 675, 676, 700];
    const seen = [];
    let twoPane = false;
    for (const width of widths) {
      twoPane = nextTwoPane(twoPane, width, 1194);
      seen.push(twoPane);
    }
    expect(seen).toEqual([false, true, true, true, true, false, false, true]);
  });
});

describe("isFullBleed", () => {
  it.each([
    "/onboarding",
    "/pair",
    "/paired",
    "/biometric",
    "/debug",
    "/debug/aln",
  ])("%s owns the whole window", (pathname) => {
    expect(isFullBleed(pathname)).toBe(true);
  });

  it.each(["/", "/chat/doc", "/outputs", "/settings", "/profile/doc/settings"])(
    "%s keeps the sidebar",
    (pathname) => {
      expect(isFullBleed(pathname)).toBe(false);
    },
  );

  it("ignores query strings and trailing slashes", () => {
    expect(isFullBleed("/pair?token=abc")).toBe(true);
    expect(isFullBleed("/debug/aln/")).toBe(true);
  });
});

describe("isPaneRoot", () => {
  it.each(["/", "/chat/doc", "/wg/wg-1", "/settings", "/outputs"])(
    "%s is a detail pane root",
    (pathname) => {
      expect(isPaneRoot(pathname)).toBe(true);
    },
  );

  it.each([
    "/wg/wg-1/settings",
    "/wg/wg-1/briefing",
    "/profile/doc",
    "/profile/doc/settings",
    "/outputs/doc/out-1",
    "/onboarding",
  ])("%s is not a detail pane root", (pathname) => {
    expect(isPaneRoot(pathname)).toBe(false);
  });

  it("treats notifications as a screen the pane holds, not an overlay over it", () => {
    expect(OUTPUTS_PATH).toBe("/outputs");
    expect(isPaneRoot(OUTPUTS_PATH)).toBe(true);
    expect(isPaneRoot("/outputs/")).toBe(true);
    expect(isPaneRoot("/outputs/doc/out-1")).toBe(false);
  });

  it("treats /settings as a pane root — desktop settings replaces the main pane", () => {
    expect(SETTINGS_PATH).toBe("/settings");
    expect(isPaneRoot("/settings")).toBe(true);
    expect(isPaneRoot("/settings/")).toBe(true);
    expect(isPaneRoot("/wg/wg-1/settings")).toBe(false);
    expect(isPaneRoot("/profile/doc/settings")).toBe(false);
  });

  it("ignores query strings", () => {
    expect(isPaneRoot("/chat/doc?connectionId=x")).toBe(true);
  });
});

describe("sidebarSelection", () => {
  it.each([
    ["/chat/doc", { kind: "chat", id: "doc" }],
    ["/chat/doc?connectionId=x", { kind: "chat", id: "doc" }],
    ["/wg/wg-1", { kind: "wg", id: "wg-1" }],
    ["/wg/wg-1/settings", { kind: "wg", id: "wg-1" }],
    ["/wg/wg-1/briefing?connectionId=x", { kind: "wg", id: "wg-1" }],
    ["/profile/doc", { kind: "profile", id: "doc" }],
    ["/profile/doc/brain/skills/email", { kind: "profile", id: "doc" }],
  ])("%s → %j", (pathname, expected) => {
    expect(sidebarSelection(pathname)).toEqual(expected);
  });

  it.each(["/wg/new", "/profile/new", "/profile/new?connectionId=x", "/", "/outputs", "/settings", "/pair"])(
    "%s selects nothing",
    (pathname) => {
      expect(sidebarSelection(pathname)).toBe(null);
    },
  );
});

describe("isHome", () => {
  it.each(["/", "/?connectionId=x", "//"])("%s is the pane root itself", (pathname) => {
    expect(isHome(pathname)).toBe(true);
  });

  it.each(["/chat/doc", "/wg/wg-1", "/settings", "/outputs"])(
    "%s is somewhere else already",
    (pathname) => {
      expect(isHome(pathname)).toBe(false);
    },
  );
});

describe("subjectPath", () => {
  it.each([
    [{ kind: "profile", id: "doc" }, "/chat/doc"],
    [{ kind: "workgroup", id: "wg-1" }, "/wg/wg-1"],
  ])("%j → %s", (item, expected) => {
    expect(subjectPath(item)).toBe(expected);
  });

  it.each([null, undefined, {}, { kind: "profile" }])("%j addresses nothing", (item) => {
    expect(subjectPath(item)).toBe(null);
  });
});

describe("resumePath", () => {
  const doc = { kind: "profile", id: "doc", sortKey: 200 };
  const wg = { kind: "workgroup", id: "wg-1", sortKey: 300 };
  const fresh = { kind: "profile", id: "vera", sortKey: 0 };

  it("takes the head of the roster, which useInbox already sorts newest-first", () => {
    expect(resumePath([doc, fresh])).toBe("/chat/doc");
  });

  it("resumes a workgroup when the newest subject is one", () => {
    expect(resumePath([wg, doc])).toBe("/wg/wg-1");
  });

  it("walks past subjects that were never touched — a fresh profile is no session", () => {
    expect(resumePath([fresh, doc])).toBe("/chat/doc");
  });

  it.each([[[]], [[fresh]], [undefined], [null]])(
    "%j leaves nothing to resume",
    (items) => {
      expect(resumePath(items)).toBe(null);
    },
  );
});

describe("openVerb", () => {
  it.each([
    [false, "/", "push"],
    [false, "/outputs", "push"],
    [false, "/settings", "push"],
    [false, "/wg/wg-1/settings", "push"],
    [true, "/", "replace"],
    [true, "/chat/doc", "replace"],
    [true, "/settings", "replace"],
    [true, "/outputs", "replace"],
    [true, "/outputs/doc/out-1", "push"],
    [true, "/wg/wg-1/settings", "push"],
    [true, "/profile/doc/settings", "push"],
  ])("twoPane=%s at %s → %s", (twoPane, pathname, expected) => {
    expect(openVerb({ twoPane, pathname })).toBe(expected);
  });
});
