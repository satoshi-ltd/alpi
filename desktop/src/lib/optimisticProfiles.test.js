import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import * as shared from "../../../common/optimisticProfiles.mjs";
import * as wrapper from "./optimisticProfiles.js";
import {
  DETAIL_ONLY_FIELDS,
  _resetProfileEdits,
  applyEdits,
  applyEditsToRows,
  beginEdit,
  confirmEdit,
  editClock,
  failEdit,
  releaseConfirmed,
  releaseLanded,
  saveOptimistic,
} from "../../../common/optimisticProfiles.mjs";

const rows = [{ name: "doc", shape: "bell", accent: "#3899e2" }];
const shapeOf = (conn = "local") => applyEditsToRows(rows, conn)[0].shape;

beforeEach(() => _resetProfileEdits());

describe("optimistic profile edits", () => {
  it("overlays a pending value on the roster of its connection only", () => {
    beginEdit("local", "doc", { shape: "heart" });
    expect(shapeOf()).toBe("heart");
    expect(shapeOf("remote")).toBe("bell");
    expect(rows[0].shape).toBe("bell");
  });

  it("falls back to the earlier pending choice when the later one fails", () => {
    beginEdit("local", "doc", { shape: "heart" });
    const second = beginEdit("local", "doc", { shape: "cloud" });
    expect(failEdit(second)).toBe(true);
    expect(shapeOf()).toBe("heart");
  });

  it("an older answer neither wins nor clears the newer choice", () => {
    const first = beginEdit("local", "doc", { shape: "heart" });
    beginEdit("local", "doc", { shape: "cloud" });
    expect(confirmEdit(first)).toBe(false);
    expect(failEdit(first)).toBe(false);
    expect(shapeOf()).toBe("cloud");
  });

  it("a roster fetched before the confirmation keeps the overlay; one fetched after releases it", () => {
    const ticket = beginEdit("local", "doc", { shape: "heart" });
    const before = editClock();
    confirmEdit(ticket);
    releaseConfirmed("local", before);
    expect(shapeOf()).toBe("heart");
    releaseConfirmed("local", editClock());
    expect(shapeOf()).toBe("bell");
  });

  it("never releases a pending edit", () => {
    beginEdit("local", "doc", { shape: "heart" });
    releaseConfirmed("local", editClock());
    expect(shapeOf()).toBe("heart");
  });

  it("releases only the paths the fetch owns", () => {
    const ticket = beginEdit("local", "doc", { vision_model: "x/y" });
    confirmEdit(ticket);
    releaseConfirmed("local", editClock(), (_name, path) => path in rows[0]);
    expect(applyEdits({ name: "doc" }, "local").vision_model).toBe("x/y");
    releaseConfirmed("local", editClock());
    expect(applyEdits({ name: "doc" }, "local").vision_model).toBeUndefined();
  });

  it("patches nested tier paths without touching siblings", () => {
    beginEdit("local", "doc", { "tiers.fast.model": "a/b" });
    const profile = { name: "doc", tiers: { fast: { model: "", effort: "low" }, deep: { model: "c/d" } } };
    const next = applyEdits(profile, "local");
    expect(next.tiers).toEqual({ fast: { model: "a/b", effort: "low" }, deep: { model: "c/d" } });
    expect(profile.tiers.fast.model).toBe("");
  });

  it("does not invent summary fields the roster row lacks", () => {
    beginEdit("local", "doc", { vision_model: "x/y" });
    expect("vision_model" in applyEditsToRows(rows, "local")[0]).toBe(false);
  });

  it("rolls back a failed save even without a failure callback", async () => {
    const saving = saveOptimistic({ connectionId: "local", name: "doc", patch: { shape: "heart" }, run: () => Promise.reject(new Error("no")) });
    expect(shapeOf()).toBe("heart");
    await expect(saving).rejects.toThrow("no");
    expect(shapeOf()).toBe("bell");
  });

  it("reports whether a confirmed save is still the latest choice", async () => {
    let finishFirst;
    const first = saveOptimistic({ connectionId: "local", name: "doc", patch: { shape: "heart" }, run: () => new Promise((r) => { finishFirst = r; }) });
    const second = saveOptimistic({ connectionId: "local", name: "doc", patch: { shape: "cloud" }, run: () => Promise.resolve() });
    finishFirst();
    expect((await first).latest).toBe(false);
    expect((await second).latest).toBe(true);
    expect(shapeOf()).toBe("cloud");
  });

  it("sends saves of one field in order, so the daemon ends at the last choice", async () => {
    const sent = [];
    const answers = [];
    const run = (value) => () => {
      sent.push(value);
      return new Promise((resolve) => answers.push(resolve));
    };
    const first = saveOptimistic({ connectionId: "local", name: "doc", patch: { budget_daily_usd: 5 }, run: run(5) });
    const second = saveOptimistic({ connectionId: "local", name: "doc", patch: { budget_daily_usd: 10 }, run: run(10) });
    const other = saveOptimistic({ connectionId: "local", name: "doc", patch: { shape: "heart" }, run: run("heart") });
    expect(sent).toEqual([5, "heart"]);
    answers[0]();
    await first;
    await vi.waitFor(() => expect(sent).toEqual([5, "heart", 10]));
    answers[1]();
    answers[2]();
    await Promise.all([second, other]);
  });

  it("keeps the order after an earlier save of the same field fails", async () => {
    const sent = [];
    const first = saveOptimistic({ connectionId: "local", name: "doc", patch: { shape: "heart" }, run: () => { sent.push("heart"); return Promise.reject(new Error("no")); } });
    const second = saveOptimistic({ connectionId: "local", name: "doc", patch: { shape: "cloud" }, run: () => { sent.push("cloud"); return Promise.resolve(); } });
    await expect(first).rejects.toThrow("no");
    expect((await second).latest).toBe(true);
    expect(sent).toEqual(["heart", "cloud"]);
  });

  it("refreshes and releases a confirmed older choice when the newer one fails", async () => {
    const budget = () => applyEdits({ name: "doc", budget_daily_usd: daemon }, "local").budget_daily_usd;
    let daemon = 1;
    let rejectB;
    const refresh = vi.fn(async () => {
      const since = editClock();
      daemon = 7;
      releaseLanded("local", since, [{ name: "doc", budget_daily_usd: daemon }]);
    });
    const a = saveOptimistic({ connectionId: "local", name: "doc", patch: { budget_daily_usd: 5 }, run: () => Promise.resolve(), refresh });
    const b = saveOptimistic({ connectionId: "local", name: "doc", patch: { budget_daily_usd: 10 }, run: () => new Promise((_, reject) => { rejectB = reject; }), refresh });
    expect((await a).latest).toBe(false);
    expect(budget()).toBe(10);
    await vi.waitFor(() => expect(rejectB).toBeTypeOf("function"));
    rejectB(new Error("no"));
    await expect(b).rejects.toThrow("no");
    await vi.waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
    await vi.waitFor(() => expect(budget()).toBe(7));
  });

  it("a refresh that fails or read before the confirmation leaves a confirmed survivor in place", async () => {
    const budget = () => applyEdits({ name: "doc", budget_daily_usd: 1 }, "local").budget_daily_usd;
    const before = editClock();
    let rejectB;
    const refresh = vi.fn(() => Promise.reject(new Error("offline")));
    const a = saveOptimistic({ connectionId: "local", name: "doc", patch: { budget_daily_usd: 5 }, run: () => Promise.resolve(), refresh });
    const b = saveOptimistic({ connectionId: "local", name: "doc", patch: { budget_daily_usd: 10 }, run: () => new Promise((_, reject) => { rejectB = reject; }), refresh });
    await a;
    await vi.waitFor(() => expect(rejectB).toBeTypeOf("function"));
    rejectB(new Error("no"));
    await expect(b).rejects.toThrow("no");
    await vi.waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
    await new Promise((r) => setTimeout(r, 0));
    expect(budget()).toBe(5);
    releaseLanded("local", before, [{ name: "doc", budget_daily_usd: 1 }]);
    expect(budget()).toBe(5);
    releaseLanded("local", editClock(), [{ name: "doc", budget_daily_usd: 5 }]);
    expect(budget()).toBe(1);
  });

  it("a confirmed save stays shown until a read that started after it lands", async () => {
    const before = editClock();
    const { latest } = await saveOptimistic({ connectionId: "local", name: "doc", patch: { shape: "heart" }, run: () => Promise.resolve() });
    expect(latest).toBe(true);
    releaseLanded("local", before, rows);
    expect(shapeOf()).toBe("heart");
    releaseLanded("local", editClock(), rows);
    expect(shapeOf()).toBe("bell");
  });

  it("does not send a queued choice that a newer one replaced before its turn", async () => {
    const sent = [];
    let finishFirst;
    const run = (value) => () => {
      sent.push(value);
      return value === "heart" ? new Promise((r) => { finishFirst = r; }) : Promise.resolve();
    };
    const saves = ["heart", "cloud", "pebble", "drop", "bean"].map((shape) =>
      saveOptimistic({ connectionId: "local", name: "doc", patch: { shape }, run: run(shape) }));
    expect(sent).toEqual(["heart"]);
    finishFirst();
    const results = await Promise.all(saves);
    expect(sent).toEqual(["heart", "bean"]);
    expect(results.map((r) => r.latest)).toEqual([false, false, false, false, true]);
    expect(shapeOf()).toBe("bean");
  });

  it("a skipped choice never resurfaces when the newer one fails", async () => {
    let finishFirst;
    let rejectLast;
    const a = saveOptimistic({ connectionId: "local", name: "doc", patch: { shape: "heart" }, run: () => new Promise((r) => { finishFirst = r; }) });
    const b = saveOptimistic({ connectionId: "local", name: "doc", patch: { shape: "cloud" }, run: () => Promise.resolve() });
    const c = saveOptimistic({ connectionId: "local", name: "doc", patch: { shape: "pebble" }, run: () => new Promise((_, reject) => { rejectLast = reject; }) });
    finishFirst();
    await a;
    expect((await b).latest).toBe(false);
    await vi.waitFor(() => expect(rejectLast).toBeTypeOf("function"));
    rejectLast(new Error("no"));
    await expect(c).rejects.toThrow("no");
    expect(shapeOf()).toBe("heart");
  });

  it("refreshes after the latest choice fails, even with nothing confirmed behind it", async () => {
    const refresh = vi.fn();
    const saving = saveOptimistic({ connectionId: "local", name: "doc", patch: { shape: "heart" }, run: () => Promise.reject(new Error("no")), refresh });
    await expect(saving).rejects.toThrow("no");
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(shapeOf()).toBe("bell");
  });

  it("does not refresh when a superseded choice fails", async () => {
    const refresh = vi.fn();
    const first = saveOptimistic({ connectionId: "local", name: "doc", patch: { shape: "heart" }, run: () => Promise.reject(new Error("no")), refresh });
    const second = saveOptimistic({ connectionId: "local", name: "doc", patch: { shape: "cloud" }, run: () => new Promise(() => {}) });
    await expect(first).rejects.toThrow("no");
    expect(refresh).not.toHaveBeenCalled();
    expect(shapeOf()).toBe("cloud");
    void second;
  });

  it("a later edit replaces an earlier one on an enclosing or enclosed path", () => {
    const profile = { name: "doc", tiers: { fast: { model: "m/0", effort: "low" } } };
    beginEdit("local", "doc", { "tiers.fast.model": "m/a" });
    beginEdit("local", "doc", { "tiers.fast": { model: "", effort: "" } });
    expect(applyEdits(profile, "local").tiers.fast.model).toBe("");
    beginEdit("local", "doc", { "tiers.fast.model": "m/b" });
    expect(applyEdits(profile, "local").tiers.fast.model).toBe("m/b");
  });

  it("clear, then a model pick while an earlier tier write is in flight, still sends the unset", async () => {
    const sent = [];
    let finishFirst;
    const save = (patch, label, wait = false) => saveOptimistic({
      connectionId: "local",
      name: "doc",
      patch,
      run: () => {
        sent.push(label);
        return wait ? new Promise((r) => { finishFirst = r; }) : Promise.resolve();
      },
    });
    const effort = save({ "tiers.fast.effort": "high" }, "effort", true);
    const clear = save({ "tiers.fast": { model: "", effort: "", reasoning_supported: false } }, "clear");
    const model = save({ "tiers.fast.model": "m/new" }, "model");
    finishFirst();
    await Promise.all([effort, clear, model]);
    expect(sent).toEqual(["effort", "clear", "model"]);
    const profile = { name: "doc", tiers: { fast: { model: "m/old", effort: "low" } } };
    expect(applyEdits(profile, "local").tiers.fast).toEqual({ model: "m/new", effort: "", reasoning_supported: false });
  });

  it("a queued tier write is skipped only when an equal or enclosing path replaces it", async () => {
    const sent = [];
    let finishFirst;
    const save = (patch, label, wait = false) => saveOptimistic({
      connectionId: "local",
      name: "doc",
      patch,
      run: () => {
        sent.push(label);
        return wait ? new Promise((r) => { finishFirst = r; }) : Promise.resolve();
      },
    });
    const saves = [
      save({ "tiers.fast.effort": "high" }, "first", true),
      save({ "tiers.fast.model": "m/a" }, "narrow"),
      save({ "tiers.fast": { model: "m/b", effort: "" } }, "clear"),
    ];
    finishFirst();
    const results = await Promise.all(saves);
    expect(sent).toEqual(["first", "clear"]);
    expect(results.map((r) => r.latest)).toEqual([false, false, true]);
  });

  it("releases what a landed fetch carries, optionally only the detail-only fields", () => {
    const tier = beginEdit("local", "doc", { "tiers.fast.model": "m/a" });
    const shape = beginEdit("local", "doc", { shape: "heart" });
    confirmEdit(tier);
    confirmEdit(shape);
    releaseLanded("local", editClock(), [{ name: "doc", shape: "bell", tiers: {} }], DETAIL_ONLY_FIELDS);
    expect(applyEdits({ name: "doc" }, "local").tiers).toBeUndefined();
    expect(shapeOf()).toBe("heart");
    releaseLanded("local", editClock(), rows);
    expect(shapeOf()).toBe("bell");
  });
});

describe("the desktop wrapper", () => {
  it("re-exports the one shared store and re-renders on every edit", () => {
    for (const name of Object.keys(shared)) expect(wrapper[name], name).toBe(shared[name]);
    const { result } = renderHook(() => wrapper.useProfileEdits());
    const before = result.current;
    act(() => {
      beginEdit("local", "doc", { shape: "heart" });
    });
    expect(result.current).toBeGreaterThan(before);
  });
});
