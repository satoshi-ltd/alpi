export const COST_CASES = [
  [null, "0 · $0.0000"],
  [{}, "0 · $0.0000"],
  [{ tokens: 1500, usd: 0.36 }, "1.5K · $0.36"],
  [{ tokens: 200, usd: 0.0042 }, "200 · $0.0042"],
  [{ tokens: 0, usd: 0.01 }, "0 · $0.01"],
];

export const SCHEDULE_CASES = [
  [null, "?"],
  [{ kind: "cron", expression: "0 9 * * 1" }, "0 9 * * 1"],
  [{ kind: "once", run_at: "2026-12-31T23:59" }, "once 2026-12-31T23:59"],
  [{ kind: "inactivity", after_hours: 0 }, "after 0h"],
  [{ kind: "inactivity" }, "after ?h"],
  [{ kind: "future-kind" }, "future-kind"],
];
