import { describe, expect, it } from "vitest";
import { isComposing } from "./composition.js";

describe("isComposing", () => {
  it("is true while an input method is composing, on the React and the native event", () => {
    expect(isComposing({ nativeEvent: { isComposing: true } })).toBe(true);
    expect(isComposing({ isComposing: true })).toBe(true);
    expect(isComposing({ keyCode: 229 })).toBe(true);
  });

  it("is false for a plain key press and for nothing", () => {
    expect(isComposing({ key: "Enter", keyCode: 13, nativeEvent: { isComposing: false } })).toBe(false);
    expect(isComposing(undefined)).toBe(false);
  });
});
