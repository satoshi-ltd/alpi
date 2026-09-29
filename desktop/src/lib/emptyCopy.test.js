import { describe, expect, it } from "vitest";
import { EMPTY, emptyLine, usageRangeEmpty } from "../../../common/emptyCopy.mjs";

describe("common/emptyCopy.mjs", () => {
  it("speaks in one voice: sentence-case title, lowercase hint, no trailing period", () => {
    for (const [key, { title, hint }] of Object.entries(EMPTY)) {
      expect(title[0], key).toBe(title[0].toUpperCase());
      expect(hint[0], key).toBe(hint[0].toLowerCase());
      expect(title.endsWith("."), key).toBe(false);
      expect(hint.endsWith("."), key).toBe(false);
    }
  });

  it("joins title and hint for inline rows and names the usage range", () => {
    expect(emptyLine("email")).toBe("No email accounts yet · connect one so the agent can read and send mail");
    expect(usageRangeEmpty(14)).toBe("No usage in the last 14 days");
    expect(usageRangeEmpty(1)).toBe("No usage in the last 1 day");
  });
});
