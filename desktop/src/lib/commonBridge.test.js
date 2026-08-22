import { describe, expect, it } from "vitest";
import { pluralize } from "../../../common/pluralize.mjs";

describe("common/ shared source directory", () => {
  it("resolves a module that lives outside the desktop root", () => {
    expect(typeof pluralize).toBe("function");
  });

  it("selects singular only for exactly one", () => {
    expect(pluralize(1, "tool call")).toBe("tool call");
    expect(pluralize(0, "tool call")).toBe("tool calls");
    expect(pluralize(2, "tool call")).toBe("tool calls");
  });

  it("honours an explicit plural form", () => {
    expect(pluralize(1, "entry", "entries")).toBe("entry");
    expect(pluralize(3, "entry", "entries")).toBe("entries");
  });
});
