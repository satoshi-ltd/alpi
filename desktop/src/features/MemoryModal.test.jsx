import { describe, it, expect, vi } from "vitest";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));

import { humanBytes, stripMemoryDelimiters, matchesFile } from "./MemoryModal.jsx";

describe("humanBytes", () => {
  it("formats by magnitude", () => {
    expect(humanBytes(0)).toBe("0b");
    expect(humanBytes(891)).toBe("891b");
    expect(humanBytes(1536)).toBe("1.5kb");
    expect(humanBytes(2 * 1024 * 1024)).toBe("2.0mb");
  });
});

describe("stripMemoryDelimiters", () => {
  it("drops the § entry delimiter and collapses blank runs", () => {
    expect(stripMemoryDelimiters("a\n§\nb")).toBe("a\n\nb");
    expect(stripMemoryDelimiters("a\n\n\n\nb")).toBe("a\n\nb");
  });
});

describe("matchesFile", () => {
  const file = { name: "AGENT.md", label: "Things alpi is", content: "ancestral worldview" };
  it("matches name, label, content; empty query passes", () => {
    expect(matchesFile(file, "")).toBe(true);
    expect(matchesFile(file, "agent")).toBe(true);
    expect(matchesFile(file, "things")).toBe(true);
    expect(matchesFile(file, "worldview")).toBe(true);
    expect(matchesFile(file, "nope")).toBe(false);
  });
});
