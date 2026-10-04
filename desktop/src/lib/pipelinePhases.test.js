import { describe, expect, it } from "vitest";
import {
  chainChips,
  hasPhaseOwners,
  liveChip,
  orderedPipelines,
  ownedPhases,
  phaseCostLine,
  phaseOwner,
  pipelineTrigger,
  runChips,
  runProgress,
  runSummary,
  runSummaryLine,
} from "../../../common/pipelinePhases.mjs";

const PIPELINES = {
  "media-update": ["media-update", "media-build", "media-qa"],
  setup: ["setup", "enrich", "intake", "qa"],
};
const PHASE_MAP = {
  setup: { owner: "pixel", task: "init" },
  enrich: { owner: "scout" },
  intake: { owner: "scout" },
  qa: { owner: "lens" },
  "media-update": { owner: "muse" },
  "media-build": { owner: "pixel" },
  "media-qa": { owner: "lens" },
};
const RUN = {
  pipeline: "setup",
  status: "running",
  cost: { usd: 2.414, tokens: 10 },
  phases: [
    { slug: "setup", state: "completed" },
    { slug: "enrich", state: "skipped" },
    { slug: "intake", state: "current" },
    { slug: "qa", state: "pending" },
  ],
};

describe("pipeline phases", () => {
  it("puts the launch chain first, keeps keys as written and names the trigger", () => {
    expect(orderedPipelines(PIPELINES, "setup").map((p) => [p.key, p.isLaunch])).toEqual([["setup", true], ["media-update", false]]);
    expect(pipelineTrigger(true)).toBe("starts at launch");
    expect(pipelineTrigger(false)).toBe("on demand");
  });

  it("lists the phases a member owns in pipeline order, none for the hub", () => {
    expect(ownedPhases(PHASE_MAP, PIPELINES, "setup", "pixel")).toEqual(["setup", "media-build"]);
    expect(ownedPhases(PHASE_MAP, PIPELINES, "setup", "lens")).toEqual(["qa", "media-qa"]);
    expect(ownedPhases(PHASE_MAP, PIPELINES, "setup", "mira")).toEqual([]);
    expect(ownedPhases(PHASE_MAP, PIPELINES, "setup", "Pixel")).toEqual(["setup", "media-build"]);
    expect(hasPhaseOwners(PHASE_MAP)).toBe(true);
    expect(hasPhaseOwners({})).toBe(false);
    expect(hasPhaseOwners(undefined)).toBe(false);
  });

  it("gives every chip its declared owner, and none without a declared step or phase_map", () => {
    expect(phaseOwner({ a: { owner: " " } }, "a")).toBeNull();
    expect(chainChips(["setup", "enrich"], {}, null).map((c) => c.owner)).toEqual([null, null]);
    expect(chainChips(PIPELINES.setup, PHASE_MAP, RUN).map((c) => [c.slug, c.owner, c.state])).toEqual([
      ["setup", "pixel", "completed"],
      ["enrich", "scout", "skipped"],
      ["intake", "scout", "current"],
      ["qa", "lens", "pending"],
    ]);
  });

  it("reads a blocked run's current phase as blocked, and an old done state as completed", () => {
    const blocked = { ...RUN, status: "blocked" };
    expect(chainChips(PIPELINES.setup, PHASE_MAP, blocked)[2].state).toBe("blocked");
    const legacy = { ...RUN, phases: [{ slug: "setup", state: "done" }] };
    expect(chainChips(["setup"], PHASE_MAP, legacy)[0].state).toBe("completed");
  });

  it("summarises the run on its own chain only", () => {
    expect(runSummaryLine(runSummary(RUN, "setup"))).toBe("last run running · 2 of 4 · $2.41");
    expect(runSummary(RUN, "media-update")).toBeNull();
    expect(runSummaryLine(runSummary({ ...RUN, status: "between", cost: { usd: 0 } }, "setup"))).toBe("last run between phases · 2 of 4");
    expect(runSummaryLine(runSummary({ ...RUN, cost_complete: false }, "setup"))).toBe("last run running · 2 of 4 · $2.41 (declared only)");
  });
});

describe("run chips for the chat strip", () => {
  const map = { qa: { owner: "lens", task: "audit the dist" }, build: { owner: "pixel" } };
  const run = { pipeline: "setup", status: "running", phases: [
    { slug: "build", state: "completed", seq: 212, cost: { usd: 0.01, tokens: 4120 } },
    { slug: "qa", state: "current", seq: 231 },
  ] };

  it("adds the hub's routed assignee only when it differs from the declared owner", () => {
    expect(liveChip(runChips(run, map, { slug: "qa", assignees: ["lens"] })).assignee).toBeNull();
    expect(liveChip(runChips(run, map, { slug: "qa", assignees: ["LENS", "lingua"] })).assignee).toBe("lingua");
    expect(liveChip(runChips(run, map, { slug: "build", assignees: ["lingua"] })).assignee).toBeNull();
    expect(liveChip(runChips(run, map, { slug: "qa" })).assignee).toBeNull();
  });

  it("carries task, seq and cost, and marks a blocked run's phase blocked", () => {
    const [build, qa] = runChips({ ...run, status: "blocked" }, map, null);
    expect(build).toMatchObject({ owner: "pixel", state: "completed", seq: 212, task: null });
    expect(qa).toMatchObject({ owner: "lens", state: "blocked", task: "audit the dist" });
    expect(phaseCostLine(build.cost)).toBe("$0.01 · 4,120 tokens");
    expect(phaseCostLine(null)).toBeNull();
  });

  it("counts completed and skipped phases over the run", () => {
    expect(runProgress(run)).toEqual({ done: 1, total: 2, label: "1 of 2" });
    expect(runProgress(null)).toBeNull();
    expect(runChips(null, map, null)).toEqual([]);
  });
});
