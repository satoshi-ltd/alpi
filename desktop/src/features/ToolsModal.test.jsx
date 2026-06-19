import { describe, it, expect, vi } from "vitest";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));

import { formatType, matchesTool, groupTools } from "./ToolsModal.jsx";

describe("formatType", () => {
  it("renders scalar, array and enum schemas", () => {
    expect(formatType({ type: "string" })).toBe("string");
    expect(formatType({ type: "array", items: { type: "string" } })).toBe("string[]");
    expect(formatType({ enum: ["a", "b"] })).toBe("enum: a | b");
    expect(formatType(undefined)).toBe("any");
  });
});

describe("matchesTool", () => {
  const tool = { name: "edit_file", category: "Filesystem", description: "Targeted edit" };
  it("matches name, category, description; empty passes", () => {
    expect(matchesTool(tool, "")).toBe(true);
    expect(matchesTool(tool, "edit")).toBe(true);
    expect(matchesTool(tool, "filesystem")).toBe(true);
    expect(matchesTool(tool, "targeted")).toBe(true);
    expect(matchesTool(tool, "browser")).toBe(false);
  });
});

describe("groupTools", () => {
  const order = ["Filesystem", "Web", "Memory"];
  it("groups by category and sorts by the given order, unknowns last", () => {
    const tools = [
      { name: "web_fetch", category: "Web" },
      { name: "read_file", category: "Filesystem" },
      { name: "odd", category: "Zzz" },
      { name: "memory", category: "Memory" },
    ];
    const groups = groupTools(tools, order);
    expect(groups.map((g) => g.cat)).toEqual(["Filesystem", "Web", "Memory", "Zzz"]);
    expect(groups[0].tools.map((t) => t.name)).toEqual(["read_file"]);
  });
});
