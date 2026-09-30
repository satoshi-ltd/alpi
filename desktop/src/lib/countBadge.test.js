import { describe, expect, it } from "vitest";
import { BADGE_CAP, badgeCount } from "../../../common/countBadge.mjs";

describe("badgeCount", () => {
  it("shows up to the cap and collapses anything above it", () => {
    expect(BADGE_CAP).toBe(9);
    expect(badgeCount(1)).toBe("1");
    expect(badgeCount(9)).toBe("9");
    expect(badgeCount(10)).toBe("9+");
    expect(badgeCount(250)).toBe("9+");
  });
});
