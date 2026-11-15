import { describe, it, expect, vi } from "vitest";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));

import { sizeLabel, skillMeta, firstSentence, memoryMeta, factLabel } from "../../../common/panelRow.mjs";
import {
  skillVersion,
  fileIconName,
  formatSkillDate,
  matchesSkill,
  viewerKind,
  groupSkills,
  orderTools,
  displayTool,
} from "./SkillsModal.jsx";

describe("panel row meta", () => {
  it("writes sizes as one-decimal units with a space", () => {
    expect(sizeLabel(0)).toBe("0 B");
    expect(sizeLabel(512)).toBe("512 B");
    expect(sizeLabel(4300)).toBe("4.2 KB");
    expect(sizeLabel(5 * 1024 * 1024)).toBe("5.0 MB");
  });
  it("lets a state word replace the size, danger only where it applies", () => {
    expect(skillMeta({ status: "active", size: 4300 })).toEqual({ meta: "4.2 KB", tone: null });
    expect(skillMeta({ status: "inactive", size: 4300 })).toEqual({ meta: "inactive", tone: null });
    expect(skillMeta({ status: "invalid", size: 4300 })).toEqual({ meta: "invalid", tone: "danger" });
    expect(skillMeta({ status: "active", size: 4300 }, "missing")).toEqual({ meta: "missing", tone: "danger" });
  });
  it("shows a memory's share, or the flag word in danger", () => {
    expect(memoryMeta(3200, 5000)).toEqual({ meta: "64%", tone: null });
    expect(memoryMeta(null, null)).toEqual({ meta: "", tone: null });
    expect(memoryMeta(5200, 5000, "over")).toEqual({ meta: "over", tone: "danger" });
  });
  it("keeps the first sentence of a tool description", () => {
    expect(firstSentence("Fetches a URL and returns its readable text. Use it for pages.")).toBe("Fetches a URL and returns its readable text.");
    expect(firstSentence("Reads `a` file\nfrom disk")).toBe("Reads a file from disk");
    expect(firstSentence("")).toBe("");
  });
  it("keeps underscores inside words and strips only markdown marks", () => {
    expect(firstSentence("Use recall_sessions to find past chats. More.")).toBe("Use recall_sessions to find past chats.");
    expect(firstSentence("Calls `index_workgroups` first")).toBe("Calls index_workgroups first");
    expect(firstSentence("## Reads **bold** and _soft_ and *lean* text")).toBe("Reads bold and soft and lean text");
    expect(firstSentence("> Quoted __strong__ line. Next.")).toBe("Quoted strong line.");
  });
  it("does not cut at common abbreviations", () => {
    expect(firstSentence("Search the web, e.g. news.")).toBe("Search the web, e.g. news.");
    expect(firstSentence("Pick one, i.e. the newest. Then stop.")).toBe("Pick one, i.e. the newest.");
    expect(firstSentence("Compare a vs. b, etc. and more! Rest.")).toBe("Compare a vs. b, etc. and more!");
  });
  it("writes group and fact labels in sentence case", () => {
    expect(factLabel("research")).toBe("Research");
  });
  it("moves version, origin and date into one fact", () => {
    expect(skillVersion({ version: "1.2", origin: "agent", created_at: "2026-09-14" })).toBe("v1.2 · agent · Sep 14");
    expect(skillVersion({})).toBe("agent");
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
