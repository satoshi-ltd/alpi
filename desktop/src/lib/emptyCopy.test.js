import { describe, expect, it } from "vitest";
import { EMPTY, emptyLine, postsHint, usageRangeEmpty } from "../../../common/emptyCopy.mjs";
import { emptyCopyProblems } from "../../../common/emptyCopy.rules.mjs";

describe("common/emptyCopy.mjs", () => {
  it("speaks in the shared voice", () => {
    expect(emptyCopyProblems(EMPTY)).toEqual([]);
  });

  it("catches a title or hint that breaks the rule", () => {
    expect(emptyCopyProblems({ a: { title: "no posts yet", hint: "" } })).toHaveLength(1);
    expect(emptyCopyProblems({ b: { title: "Nothing here · yet", hint: "" } })).not.toEqual([]);
    expect(emptyCopyProblems({ c: { title: "None", hint: "" } })).not.toEqual([]);
    expect(emptyCopyProblems({ d: { title: "No items", hint: "add one" } })).toHaveLength(2);
    expect(emptyCopyProblems({ e: { title: "No items", hint: "Add one — now." } })).toHaveLength(1);
    expect(emptyCopyProblems({ f: { title: "No items", hint: "Add one. Then more." } })).toHaveLength(1);
    for (const title of ["None yet", "Nothing here!", "Nothing - yet", "Empty list", "Nothing yet…"]) {
      expect(emptyCopyProblems({ g: { title, hint: "" } }), title).not.toEqual([]);
    }
    for (const hint of ["Add one—now.", "Add one - now.", "Add one; then more.", "Add one..."]) {
      expect(emptyCopyProblems({ h: { title: "No items", hint } }), hint).not.toEqual([]);
    }
    expect(emptyCopyProblems({ i: {} })).not.toEqual([]);
  });

  it("reads an inline absence as its title alone, never joined to a hint", () => {
    expect(emptyLine("email")).toBe("No email accounts yet");
    expect(emptyLine("mcpEnv")).toBe("No env keys");
  });

  it("names the hub in the thread hint and the usage range", () => {
    expect(postsHint("doc")).toBe("Direct @doc to open a #task.");
    expect(usageRangeEmpty(14)).toBe("No usage in the last 14 days");
    expect(usageRangeEmpty(1)).toBe("No usage in the last 1 day");
  });
});
