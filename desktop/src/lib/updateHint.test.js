import { describe, expect, it } from "vitest";
import { UPDATE_HINT_CASES } from "../../../common/updateHint.fixtures.mjs";
import { canSelfUpdate, updateHint } from "../../../common/updateHint.mjs";

describe("the manual update step", () => {
  it.each(UPDATE_HINT_CASES)("%s with %j reads the shared sentence", (installer, version, sentence) => {
    expect(updateHint(installer, version)).toBe(sentence);
  });

  it("hides the update button only when the daemon says it cannot self-update", () => {
    expect(canSelfUpdate(false)).toBe(false);
    expect(canSelfUpdate(true)).toBe(true);
    expect(canSelfUpdate(undefined)).toBe(true);
    expect(canSelfUpdate(null)).toBe(true);
  });
});
