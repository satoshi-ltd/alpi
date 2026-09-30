import { describe, expect, it } from "vitest";
import { PLAIN_ERROR_CASES, PLAIN_ERROR_UNTOUCHED } from "../../../common/plainError.fixtures.mjs";
import { plainError } from "../../../common/plainError.mjs";
import { describeConnectionError } from "./connection-status.js";

describe("plain words for the app's own errors", () => {
  it.each(PLAIN_ERROR_CASES)("turns %j into a sentence", (raw, sentence) => {
    expect(plainError(raw)).toBe(sentence);
    expect(describeConnectionError(raw)).toBe(sentence);
  });

  it.each(PLAIN_ERROR_UNTOUCHED)("leaves %j as it is", (raw) => {
    expect(plainError(raw)).toBe(raw);
  });

  it("tolerates a missing value", () => {
    expect(plainError(undefined)).toBe("");
    expect(plainError(null)).toBe("");
  });
});

describe("plainError limits", () => {
  it("returns an oversized message untouched and quickly", () => {
    const hostile = `${": send failed: ".repeat(200000)}\n`;
    const started = performance.now();
    expect(plainError(hostile)).toBe(hostile);
    expect(performance.now() - started).toBeLessThan(50);
  });

  it("keeps the context before a known error", () => {
    expect(plainError("Couldn't save notes.md: alp -32029: too-many-connections")).toBe(
      "Couldn't save notes.md: This device has too many open connections to the daemon. Wait a few seconds and try again.",
    );
  });
});
