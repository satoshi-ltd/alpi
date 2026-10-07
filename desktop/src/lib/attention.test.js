import { describe, expect, it } from "vitest";
import {
  attentionHelper,
  attentionItems,
  attentionLabel,
  flagCount,
  jobBanner,
  jobGroups,
  jobItem,
  memoryBanner,
  memoryItem,
  nextRunWord,
  skillBanner,
  skillItem,
  totalFlags,
} from "../../../common/attention.mjs";

const ATT = {
  memory: [{ file: "AGENT.md", used: 9454, limit: 8000, pct: 118, over: true }, { file: "USER.md", used: 2800, limit: 3000, pct: 93, over: false }],
  skills: [{ name: "review-digest", category: "research", problem: "lint", message: "name: must be kebab-case" }, { name: "needs-token", category: null, problem: "missing", message: "missing env TOKEN" }],
  schedules: [{ id: "j1", title: "Digest", message: "timeout", at: "2026-10-07T07:30:00+00:00", last_ok_at: "2026-10-06T07:30:00+00:00" }],
};

describe("attention", () => {
  it("counts what is flagged per panel and in total, tolerating an older daemon", () => {
    expect(flagCount(ATT, "memory")).toBe(2);
    expect(flagCount(ATT, "skills")).toBe(2);
    expect(flagCount(ATT, "schedule")).toBe(1);
    expect(flagCount(ATT, "tools")).toBe(0);
    expect(totalFlags(ATT)).toBe(5);
    expect(attentionItems(null, "memory")).toEqual([]);
    expect(totalFlags(undefined)).toBe(0);
  });

  it("finds an item by its identity", () => {
    expect(memoryItem(ATT, "AGENT.md").over).toBe(true);
    expect(memoryItem(ATT, "MEMORY.md")).toBeNull();
    expect(skillItem(ATT, "research", "review-digest").problem).toBe("lint");
    expect(skillItem(ATT, null, "needs-token").problem).toBe("missing");
    expect(skillItem(ATT, "research", "needs-token")).toBeNull();
    expect(jobItem(ATT, "j1").title).toBe("Digest");
  });

  it("writes the banner of each case", () => {
    expect(memoryBanner(ATT.memory[0]).lead).toBe("Over its limit by 1,454 characters");
    expect(memoryBanner(ATT.memory[1]).lead).toBe("Nearly full: 93% of its limit");
    expect(skillBanner(ATT.skills[0])).toEqual({ lead: "Does not pass lint", detail: "name: must be kebab-case. The skill is not offered to the model until it passes." });
    expect(skillBanner(ATT.skills[1]).lead).toBe("Missing what it requires");
    expect(jobBanner(ATT.schedules[0], "yesterday at 07:30")).toEqual({ lead: "Last run failed", detail: "timeout. Last good run: yesterday at 07:30." });
    expect(jobBanner({ message: "", last_ok_at: null }).detail).toBe("The run did not complete. It has not succeeded yet.");
  });

  it("summarises a section for a settings row", () => {
    expect(attentionHelper(ATT, "memory")).toBe("1 over its limit");
    expect(attentionHelper(ATT, "skills")).toBe("1 fails lint · 1 missing what it requires");
    expect(attentionHelper(ATT, "schedule")).toBe("1 failed");
    expect(attentionHelper({ memory: [], skills: [], schedules: [] }, "skills")).toBeNull();
    expect(attentionLabel(ATT, "schedule")).toBe("1 job needs you");
    expect(attentionLabel(ATT, "memory")).toBe("2 files need you");
    expect(attentionLabel(ATT, "tools")).toBe("");
  });

  it("says when a job runs next, or that it failed or is paused", () => {
    const now = Date.parse("2026-10-07T00:00:00Z");
    expect(nextRunWord({ next_fire: "2026-10-09T00:00:00Z" }, now)).toBe("in 2d");
    expect(nextRunWord({ next_fire: "2026-10-07T15:00:00Z" }, now)).toBe("in 15h");
    expect(nextRunWord({ next_fire: "2026-10-07T00:05:00Z" }, now)).toBe("in 5m");
    expect(nextRunWord({ next_fire: "2026-10-07T00:00:10Z" }, now)).toBe("now");
    expect(nextRunWord({ next_fire: null }, now)).toBe("");
    expect(nextRunWord({ paused: true, next_fire: "2026-10-09T00:00:00Z" }, now)).toBe("paused");
    expect(nextRunWord({ last_run_status: "error", next_fire: "2026-10-09T00:00:00Z" }, now)).toBe("failed");
  });

  it("groups jobs under Needs you, Active and Paused and drops the empty ones", () => {
    const jobs = [{ id: "a" }, { id: "b", last_run_status: "error" }, { id: "c", paused: true, last_run_status: "error" }, { id: "d" }];
    const groups = jobGroups(jobs);
    expect(groups.map((g) => [g.label, g.jobs.map((j) => j.id)])).toEqual([["Needs you", ["b"]], ["Active", ["a", "d"]], ["Paused", ["c"]]]);
    expect(jobGroups([{ id: "a" }]).map((g) => g.id)).toEqual(["active"]);
    expect(jobGroups(null)).toEqual([]);
  });
});
