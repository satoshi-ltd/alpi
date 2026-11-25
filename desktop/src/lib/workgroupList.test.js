import { describe, expect, it } from "vitest";
import {
  filterCounts,
  groupWorkgroupRows,
  inFilter,
  noMatchLine,
  rosterWorkgroups,
  workgroupRowState,
  workgroupStatusLabel,
} from "../../../common/workgroupList.mjs";

const state = (workgroup, extra = {}) => workgroupRowState({ workgroup: { id: "w", ...workgroup }, ...extra }).state;

describe("workgroup list", () => {
  it("names each state with the label the row shows", () => {
    expect(state({ paused: true })).toEqual({ id: "paused", label: "Paused" });
    expect(state({ pipeline_status: "queued", queue_position: 12 })).toEqual({ id: "queued", label: "Queued · #12" });
    expect(state({ pipeline_status: "blocked" }).id).toBe("needs");
    expect(state({ pipeline_status: "running", pipeline_phase: "build", phase_map: { build: { owner: "@pixel" } } })).toEqual({ id: "active", label: "Working · build · @pixel" });
    expect(state({}, { task: { state: "error" } })).toEqual({ id: "error", label: "Needs attention" });
    expect(state({}, { busy: true }).id).toBe("active");
    expect(state({}, { run: { phase: "build", phasesDone: 1, phasesTotal: 3 } })).toEqual({ id: "active", label: "Working · build" });
    expect(state({}, { task: { state: "open", slug: "assets" } })).toEqual({ id: "active", label: "Working" });
    expect(filterCounts([state({}, { run: { phasesDone: 0, phasesTotal: 2 } }).id]).active).toBe(1);
    expect(state({ pipeline_status: "completed" }).id).toBe("idle");
  });

  it("counts every filter over the whole set, with needs you and attention under Working", () => {
    expect(filterCounts(["active", "needs", "error", "queued", "idle", "idle", "paused"])).toEqual({ all: 7, active: 3, queued: 1, paused: 1 });
    expect(filterCounts(Array(59).fill("idle"))).toEqual({ all: 59, active: 0, queued: 0, paused: 0 });
    expect(inFilter("needs", "active")).toBe(true);
    expect(inFilter("idle", "active")).toBe(false);
  });

  it("groups rows in the table's order and drops the empty groups", () => {
    const rows = ["idle", "queued", "error", "active", "paused", "needs"].map((id, i) => ({ key: i, state: { id } }));
    const groups = groupWorkgroupRows(rows);
    expect(groups.map((g) => g.label)).toEqual(["Needs you", "Working", "Queued", "Idle", "Paused"]);
    expect(groups[0].rows.map((r) => r.state.id)).toEqual(["error", "needs"]);
    expect(groupWorkgroupRows([{ state: { id: "idle" } }]).map((g) => g.id)).toEqual(["idle"]);
  });

  it("keeps the label for every state but idle", () => {
    expect(workgroupStatusLabel({ id: "idle", label: "Idle" })).toBeNull();
    expect(workgroupStatusLabel({ id: "queued", label: "Queued · #2" })).toBe("Queued · #2");
  });

  it("answers an empty view with one line", () => {
    expect(noMatchLine("paused", " deploy ")).toBe("No paused workgroup matches deploy.");
    expect(noMatchLine("all", "x")).toBe("No workgroup matches x.");
    expect(noMatchLine("queued", "")).toBe("No queued workgroups right now.");
  });

  it("keeps every moving workgroup in the roster and fills up to the cap with the most recent idle ones", () => {
    const rows = [
      { id: "a", stateId: "idle" }, { id: "b", stateId: "queued" }, { id: "c", stateId: "idle" },
      { id: "d", stateId: "active" }, { id: "e", stateId: "idle" }, { id: "f", stateId: "idle" }, { id: "g", stateId: "paused" },
    ];
    expect(rosterWorkgroups(rows, 5).map((r) => r.id)).toEqual(["d", "b", "a", "c", "e"]);
    const queued = [{ id: "q3", stateId: "queued", raw: { queue_position: 3 } }, { id: "q1", stateId: "queued", raw: { queue_position: 1 } }];
    expect(rosterWorkgroups([...queued, { id: "i", stateId: "idle" }], 5).map((r) => r.id)).toEqual(["q1", "q3", "i"]);
    const busy = Array.from({ length: 7 }, (_, i) => ({ id: `n${i}`, stateId: "needs" }));
    expect(rosterWorkgroups([...busy, { id: "z", stateId: "idle" }], 5).map((r) => r.id)).toEqual(busy.map((r) => r.id));
  });
});
