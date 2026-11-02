import { describe, expect, it } from "vitest";
import {
  MAX_FALLBACKS,
  addFallback,
  fallbackCandidates,
  fallbackList,
  hasFallbackModels,
  moveFallback,
  removeFallback,
} from "../../../common/fallbackModels.mjs";

describe("fallback models", () => {
  it("reads the row as present only when the daemon sends the list", () => {
    expect(hasFallbackModels({})).toBe(false);
    expect(hasFallbackModels({ fallback_models: null })).toBe(false);
    expect(hasFallbackModels({ fallback_models: [] })).toBe(true);
    expect(fallbackList({ fallback_models: ["a/x", "", 3, "b/y"] })).toEqual(["a/x", "b/y"]);
    expect(fallbackList(null)).toEqual([]);
  });

  it("drops the main model from the list so edits after a promotion are accepted", () => {
    expect(fallbackList({ model: "b/y", fallback_models: ["a/x", "b/y", "c/z"] })).toEqual(["a/x", "c/z"]);
  });

  it("stops adding at the daemon's cap", () => {
    const full = Array.from({ length: MAX_FALLBACKS }, (_, i) => `p/m${i}`);
    expect(MAX_FALLBACKS).toBe(16);
    expect(addFallback(full, "p/extra", "m/main")).toBe(full);
    expect(addFallback(full.slice(1), "p/extra", "m/main")).toHaveLength(16);
  });

  it("adds a model once and never the main model", () => {
    expect(addFallback(["a/x"], "b/y", "m/main")).toEqual(["a/x", "b/y"]);
    expect(addFallback(["a/x"], "a/x", "m/main")).toEqual(["a/x"]);
    expect(addFallback(["a/x"], "m/main", "m/main")).toEqual(["a/x"]);
    expect(fallbackCandidates(["m/main", "a/x", "b/y", ""], ["a/x"], "m/main")).toEqual(["b/y"]);
  });

  it("moves and removes by position, ignoring moves past either end", () => {
    const list = ["a/x", "b/y", "c/z"];
    expect(moveFallback(list, 2, -1)).toEqual(["a/x", "c/z", "b/y"]);
    expect(moveFallback(list, 0, 1)).toEqual(["b/y", "a/x", "c/z"]);
    expect(moveFallback(list, 0, -1)).toBe(list);
    expect(moveFallback(list, 2, 1)).toBe(list);
    expect(removeFallback(list, 1)).toEqual(["a/x", "c/z"]);
  });
});
