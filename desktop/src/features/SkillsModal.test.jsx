import { describe, it, expect, vi } from "vitest";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));

import {
  formatBytes,
  fileIconName,
  formatSkillDate,
  matchesSkill,
  viewerKind,
  groupSkills,
  orderTools,
  displayTool,
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
  it("gives every file its type, never the folder icon", () => {
    expect(fileIconName({ name: "SKILL.md", kind: "file", ftype: "skill" })).toBe("file-text");
    expect(fileIconName({ name: "normalize.py", kind: "file", ftype: "py" })).toBe("file-code");
    expect(fileIconName({ name: "fields.json", kind: "file", ftype: "text" })).toBe("file-code");
    expect(fileIconName({ name: "rules.yaml", kind: "file", ftype: "text" })).toBe("file-code");
    expect(fileIconName({ name: "db.sqlite", kind: "file", ftype: "binary" })).toBe("database");
    expect(fileIconName({ name: "cache.db", kind: "file", ftype: "binary" })).toBe("database");
    expect(fileIconName({ name: "photo.png", kind: "file", ftype: "binary" })).toBe("file");
    expect(fileIconName({ name: "state", kind: "dir" })).toBe("folder");
    expect(fileIconName({ name: "secrets", kind: "dir", locked: true })).toBe("lock");
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

describe("tool ordering and display", () => {
  it("orders alpi built-ins before mcp tools, stable within groups", () => {
    expect(orderTools(["lobby__a", "web_search", "lobby__b", "notify"]))
      .toEqual(["web_search", "notify", "lobby__a", "lobby__b"]);
  });

  it("renders mcp tools with a middot separator, built-ins unchanged", () => {
    expect(displayTool("lobby__lobby_list_channels")).toBe("lobby.lobby_list_channels");
    expect(displayTool("web_search")).toBe("web_search");
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
