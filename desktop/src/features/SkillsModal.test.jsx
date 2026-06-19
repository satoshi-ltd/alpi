import { describe, it, expect, vi } from "vitest";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));

import {
  formatBytes,
  fileIconName,
  formatSkillDate,
  matchesSkill,
  viewerKind,
  groupSkills,
} from "./SkillsModal.jsx";

describe("formatBytes", () => {
  it("shows raw bytes under 1kb", () => {
    expect(formatBytes(0)).toBe("0b");
    expect(formatBytes(512)).toBe("512b");
  });
  it("shows one-decimal kb", () => {
    expect(formatBytes(1024)).toBe("1.0kb");
    expect(formatBytes(3400)).toBe("3.3kb");
  });
  it("rolls over to mb", () => {
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0mb");
  });
});

describe("fileIconName", () => {
  it("maps ftype to an icon", () => {
    expect(fileIconName("skill")).toBe("sparkle");
    expect(fileIconName("py")).toBe("cpu");
    expect(fileIconName("md")).toBe("eye");
    expect(fileIconName("text")).toBe("eye");
    expect(fileIconName("binary")).toBe("folder");
  });
});

describe("formatSkillDate", () => {
  it("renders Mon DD from an ISO date", () => {
    expect(formatSkillDate("2026-04-20")).toBe("Apr 20");
    expect(formatSkillDate("2026-02-18")).toBe("Feb 18");
  });
  it("passes through non-ISO input", () => {
    expect(formatSkillDate("")).toBe("");
    expect(formatSkillDate("soon")).toBe("soon");
  });
});

describe("matchesSkill", () => {
  const skill = {
    name: "whoop",
    category: "personal",
    description: "Sync nightly recovery",
    keywords: ["strain", "sleep"],
  };
  it("matches an empty query", () => {
    expect(matchesSkill(skill, "")).toBe(true);
  });
  it("matches id, category, keyword and description", () => {
    expect(matchesSkill(skill, "whoo")).toBe(true);
    expect(matchesSkill(skill, "personal")).toBe(true);
    expect(matchesSkill(skill, "sleep")).toBe(true);
    expect(matchesSkill(skill, "recovery")).toBe(true);
  });
  it("rejects a miss", () => {
    expect(matchesSkill(skill, "garmin")).toBe(false);
  });
});

describe("viewerKind", () => {
  it("classifies the file by ftype and binary flag", () => {
    expect(viewerKind(null)).toBe("empty");
    expect(viewerKind({ binary: true, ftype: "binary" })).toBe("binary");
    expect(viewerKind({ ftype: "skill" })).toBe("markdown");
    expect(viewerKind({ ftype: "md" })).toBe("markdown");
    expect(viewerKind({ ftype: "py" })).toBe("code");
    expect(viewerKind({ ftype: "text" })).toBe("code");
  });
});

describe("groupSkills", () => {
  it("groups by category alphabetically, uncategorized last", () => {
    const skills = [
      { name: "b", category: "personal" },
      { name: "a", category: "creative" },
      { name: "c", category: null },
      { name: "d", category: "creative" },
    ];
    const groups = groupSkills(skills);
    expect(groups.map((g) => g.cat)).toEqual(["creative", "personal", "uncategorized"]);
    expect(groups[0].skills.map((s) => s.name)).toEqual(["a", "d"]);
  });
});
