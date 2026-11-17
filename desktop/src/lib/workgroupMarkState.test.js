import { describe, expect, it } from "vitest";
import { currentCell, pipelineRunMark, withOwner, workgroupGap, workgroupStatusLine, workgroupMark, workgroupMarkAccent, workgroupMarkState, workgroupPhase, accentLookup } from "../../../common/workgroupMarkState.mjs";

describe("workgroup mark state", () => {
  it("reads the pipeline's state, paused and offline first", () => {
    expect(workgroupMarkState({ workgroup: { paused: true, pipeline_status: "running" } })).toBe("paused");
    expect(workgroupMarkState({ workgroup: { pipeline_status: "running" }, offline: true })).toBe("offline");
    expect(workgroupMarkState({ workgroup: { pipeline_status: "blocked" } })).toBe("needs");
    expect(workgroupMarkState({ workgroup: { pipeline_status: "queued" } })).toBe("queued");
    expect(workgroupMarkState({ workgroup: { pipeline_status: "between" } })).toBe("running");
    expect(workgroupMarkState({ workgroup: {}, busy: true })).toBe("running");
    expect(workgroupMarkState({ workgroup: {}, task: { state: "open" } })).toBe("running");
    expect(workgroupMarkState({ workgroup: {}, task: { state: "error" } })).toBe("failed");
    expect(workgroupMarkState({ workgroup: { pipeline_status: "completed" } })).toBe("idle");
  });

  it("takes phase counts from either the roster or the activity row", () => {
    expect(workgroupPhase({ phasesDone: 1, phasesTotal: 4 })).toEqual([1, 4]);
    expect(workgroupPhase({ phases_done: 5, phases_total: 4 })).toEqual([4, 4]);
    expect(workgroupPhase({ phasesDone: null, phasesTotal: 4 })).toBeNull();
    expect(workgroupPhase({ phasesDone: 0, phasesTotal: 0 })).toBeNull();
  });

  it("picks the cell by thirds of the pipeline", () => {
    expect([[0, 3], [1, 3], [2, 3], [3, 3], [1, 4], [2, 4]].map(currentCell)).toEqual(["left", "top", "right", "right", "left", "top"]);
    expect(currentCell(null)).toBeNull();
  });

  it("widens the gap at small sizes like the design board", () => {
    expect(workgroupGap(14)).toBe(9.3);
    expect(workgroupGap(20)).toBe(6.5);
    expect(workgroupGap(72)).toBe(5);
  });

  it("names the owner of the current phase and never hands the mark a colour", () => {
    const workgroup = { phase_map: { translate: { owner: "@lingo" } } };
    const mark = workgroupMark({ workgroup, run: { phase: "translate", phasesDone: 2, phasesTotal: 4 } });
    expect(mark).toEqual({ state: "running", phase: [2, 4], step: "translate", owner: "lingo" });
    expect(mark).not.toHaveProperty("active");
    expect(workgroupMark({ workgroup, run: { phase: "file" } }).owner).toBeNull();
    expect(workgroupMark({ workgroup: { ...workgroup, paused: true }, run: { phase: "translate" } }).owner).toBeNull();
    expect(workgroupMark({ workgroup: { ...workgroup, pipeline_status: "blocked", pipeline_phase: "translate" } })).toEqual({ state: "needs", phase: null, step: "translate", owner: "lingo" });
  });

  it("puts the owner in the meta words", () => {
    expect(withOwner("Working · translate", "lingo")).toBe("Working · translate · @lingo");
    expect(withOwner("Needs you · approval", "@yuri")).toBe("Needs you · approval · @yuri");
    expect(withOwner("Idle", null)).toBe("Idle");
    expect(workgroupStatusLine({ state: "running", step: "translate", owner: "lingua" })).toBe("Working · translate · @lingua");
    expect(workgroupStatusLine({ state: "needs", step: "approval", owner: "yuri" })).toBe("Needs you · approval · @yuri");
    expect(workgroupStatusLine({ state: "running", step: null, owner: null })).toBe("Working");
    expect(workgroupStatusLine({ state: "idle", step: null, owner: null })).toBeNull();
  });

  it("derives the same mark from a full pipeline run", () => {
    const workgroup = { pipeline_status: "running", phase_map: { b: { owner: "lingo" } } };
    const pipelineRun = { status: "running", current_phase: "b", phases: [{ slug: "a", state: "done" }, { slug: "b", state: "current" }, { slug: "c", state: "pending" }] };
    expect(pipelineRunMark({ workgroup, pipelineRun })).toEqual({ state: "running", phase: [1, 3], step: "b", owner: "lingo" });
    expect(pipelineRunMark({ workgroup, pipelineRun: { ...pipelineRun, status: "blocked" } }).state).toBe("needs");
    expect(pipelineRunMark({ workgroup, pipelineRun: { ...pipelineRun, status: "completed" } })).toEqual({ state: "idle", phase: null, step: null, owner: null });
  });
});

describe("workgroup mark accent", () => {
  const accents = { lingo: "#9b5ad9", doc: "#3899e2" };
  const accentOf = (name) => accents[name];

  it("lights the honeycomb in the accent of the profile that owns the live phase", () => {
    const workgroup = { pipeline_status: "running", phase_map: { build: { owner: "@lingo" } } };
    const mark = workgroupMark({ workgroup, run: { phasesDone: 1, phasesTotal: 3, phase: "build" } });
    expect(workgroupMarkAccent(mark, "#3899e2", accentOf)).toBe("#9b5ad9");
  });

  it("falls back to the hub when nobody owns the phase, the owner is remote or the group rests", () => {
    const hub = "#3899e2";
    const running = { pipeline_status: "running", phase_map: { build: { owner: "@peer" } } };
    expect(workgroupMarkAccent(workgroupMark({ workgroup: running, run: { phasesDone: 1, phasesTotal: 3, phase: "build" } }), hub, accentOf)).toBe(hub);
    expect(workgroupMarkAccent(workgroupMark({ workgroup: { pipeline_status: "running" } }), hub, accentOf)).toBe(hub);
    expect(workgroupMarkAccent(workgroupMark({ workgroup: { pipeline_status: "completed", pipeline_phase: "build", phase_map: { build: { owner: "lingo" } } } }), hub, accentOf)).toBe(hub);
    expect(workgroupMarkAccent({ owner: "lingo" }, hub, null)).toBe(hub);
    expect(workgroupMarkAccent(null, null, accentOf)).toBeNull();
  });
});

describe("accentLookup", () => {
  it("finds an owner whatever its case or leading @, like the daemon does", () => {
    const accentOf = accentLookup([{ name: "lingo", accent: "#9b5ad9" }, { name: "Doc", accent: "#3899e2" }]);
    expect(accentOf("@Lingo")).toBe("#9b5ad9");
    expect(accentOf("doc")).toBe("#3899e2");
    expect(accentOf("peer")).toBeNull();
    expect(accentLookup(null)("lingo")).toBeNull();
    const workgroup = { pipeline_status: "running", phase_map: { build: { owner: "@LINGO" } } };
    expect(workgroupMarkAccent(workgroupMark({ workgroup, run: { phasesDone: 1, phasesTotal: 3, phase: "build" } }), "#000000", accentOf)).toBe("#9b5ad9");
  });
});
