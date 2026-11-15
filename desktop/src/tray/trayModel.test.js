import { describe, expect, it } from "vitest";
import { MAX_NEEDS_ROWS, TRAY_STATES, trayModel, trayState } from "./trayModel.js";

const NOW = Date.UTC(2026, 9, 27, 12, 0, 0);
const sec = (agoSeconds) => (NOW - agoSeconds * 1000) / 1000;

const need = (i, over = {}) => ({
  id: `r${i}`,
  kind: "approval",
  profile: `p${i}`,
  label: `p${i}`,
  title: "wants to run a command",
  ts: sec(120),
  shape: "twin",
  accent: "#df4b9d",
  deeplink: { kind: "approval", profile: `p${i}`, id: `r${i}`, connection_id: "c1" },
  ...over,
});

const snap = (over = {}) => ({
  state: "quiet",
  member: false,
  unread: 0,
  update: null,
  needs: { total: 0, approvals: 0, questions: 0, rows: [] },
  failing: { jobs: 0, profileCount: 0, profiles: [] },
  running: { count: 0, rows: [] },
  offline: null,
  ...over,
});

const needsSnap = (n, over = {}) => {
  const rows = Array.from({ length: Math.min(n, 4) }, (_, i) => need(i));
  return snap({ state: "needs", needs: { total: n, approvals: n, questions: 0, rows }, ...over });
};

const turn = (i, over = {}) => ({ id: `t${i}`, profile: "alpi", label: "alpi", title: `Turn ${i}`, ts: NOW / 1000 - 120, shape: "llama", accent: "#14110c", deeplink: { kind: "chat", profile: "alpi", id: `s${i}`, connection_id: "c" }, ...over });

describe("trayState", () => {
  it("lets the link outrank everything and then ranks needs-you, failing, running", () => {
    expect(trayState({ link: "offline", needs: 3, failing: 1, running: 1 })).toBe("offline");
    expect(trayState({ link: "starting", needs: 3 })).toBe("starting");
    expect(trayState({ link: "connecting", needs: 3 })).toBe("connecting");
    expect(trayState({ needs: 1, failing: 2, running: 3 })).toBe("needs");
    expect(trayState({ failing: 2, running: 3 })).toBe("failing");
    expect(trayState({ running: 3 })).toBe("running");
    expect(trayState({})).toBe("quiet");
    expect(trayState()).toBe("quiet");
  });
});

describe("trayModel states", () => {
  it("draws All quiet with nothing to do", () => {
    const m = trayModel(snap(), NOW);
    expect(m).toMatchObject({ state: "quiet", title: "All quiet", sub: "Nothing needs you", rows: [], more: 0, counts: [], failing: null, busy: null, start: false, update: null, nextGroups: [] });
  });

  it("draws Needs you with the rows led by who, the failing banner and the running count", () => {
    const m = trayModel(
      needsSnap(2, { failing: { jobs: 3, profileCount: 2, profiles: ["sentinel", "clonara"] }, running: { count: 2, rows: [] }, unread: 1 }),
      NOW,
    );
    expect(m.title).toBe("2 need you");
    expect(m.sub).toBe("2 running");
    expect(m.rows).toHaveLength(2);
    expect(m.rows[0]).toMatchObject({ key: "r0", kind: "approval", title: "wants to run a command", name: "p0", connection: null, meta: "approval · 2m" });
    expect(m.rows[0]).not.toHaveProperty("sub");
    expect(m.failing).toEqual({ title: "3 jobs failed in 24 h", detail: "sentinel and clonara" });
    expect(m.counts.map((c) => [c.key, c.label, c.value, c.danger])).toEqual([["running", "Running", "2", false]]);
    expect(m).not.toHaveProperty("labels");
    expect(m.unread).toBe(1);
    expect(m.bellLabel).toBe("Notifications · 1 unread");
  });

  it("lists the running turns as rows with their fold and elapsed time", () => {
    const m = trayModel(snap({ state: "running", running: { count: 2, rows: [turn(0), turn(1, { ts: null })] } }), NOW);
    expect(m.title).toBe("Alpi is working");
    expect(m.sub).toBe("Nothing needs you");
    expect(m.runs).toEqual([
      { key: "t0", title: "Turn 0", name: "alpi", connection: null, elapsed: "2m", shape: "llama", accent: "#14110c", deeplink: { kind: "chat", profile: "alpi", id: "s0", connection_id: "c" } },
      expect.objectContaining({ key: "t1", elapsed: "" }),
    ]);
    expect(m.counts).toEqual([]);
    expect(m.runsMore).toBe(0);
  });

  it("caps running rows at four and counts the rest", () => {
    const m = trayModel(snap({ state: "running", running: { count: 7, rows: [0, 1, 2, 3, 4, 5].map((i) => turn(i)) } }), NOW);
    expect(m.runs).toHaveLength(4);
    expect(m.runsMore).toBe(3);
  });

  it("lists running rows beside one needs-you row and collapses them to a count when needs you is full", () => {
    const running = { count: 2, rows: [turn(0), turn(1)] };
    const beside = trayModel(snap({ ...needsSnap(1), running }), NOW);
    expect(beside.runs).toHaveLength(2);
    expect(beside.counts).toEqual([]);
    const full = trayModel(snap({ ...needsSnap(3), running }), NOW);
    expect(full.runs).toEqual([]);
    expect(full.counts).toEqual([{ key: "running", icon: "activity", label: "Running", value: "2", danger: false }]);
  });

  it("falls back to the Running count line without rows", () => {
    expect(trayModel(snap({ state: "running", running: { count: 2, rows: [] } }), NOW).counts).toHaveLength(1);
  });

  it("draws Failing jobs with the profiles and the Activity window", () => {
    const m = trayModel(snap({ state: "failing", failing: { jobs: 3, profileCount: 2, profiles: ["sentinel", "clonara"] } }), NOW);
    expect(m.title).toBe("3 jobs failing");
    expect(m.sub).toBe("Nothing needs you");
    expect(m.failing).toEqual({ title: "3 jobs failed in 24 h", detail: "sentinel and clonara" });
    expect(m.counts).toEqual([]);
  });

  it("draws a stopped daemon with its one action", () => {
    const m = trayModel(snap({ state: "offline", offline: { local: true, canStart: true, absent: false } }), NOW);
    expect(m).toMatchObject({ title: "alpi isn’t running", sub: "It is installed on this computer.", start: true, rows: [], counts: [], failing: null });
  });

  it("draws Starting with the request row and no action", () => {
    const m = trayModel(snap({ state: "starting" }), NOW);
    expect(m).toMatchObject({ title: "Starting alpi…", sub: "Waiting for the daemon", busy: "Start requested", start: false });
  });

  it("draws the update row on a quiet popover", () => {
    const m = trayModel(snap({ update: { version: "0.9.3", busy: false } }), NOW);
    expect(m.title).toBe("All quiet");
    expect(m.update).toEqual({ text: "alpi 0.9.3 is ready", busy: false });
  });

  it("draws Many items as four rows, the rest named, and the kinds counted", () => {
    const m = trayModel(
      needsSnap(7, { needs: { total: 7, approvals: 5, questions: 2, rows: Array.from({ length: 4 }, (_, i) => need(i)) }, unread: 4 }),
      NOW,
    );
    expect(m.title).toBe("7 need you");
    expect(m.sub).toBe("5 approvals, 2 questions");
    expect(m.rows).toHaveLength(MAX_NEEDS_ROWS);
    expect(m.more).toBe(3);
  });

  it("covers every state it declares", () => {
    for (const state of TRAY_STATES) expect(trayModel(snap({ state }), NOW).state).toBe(state);
  });

  it("reads an unknown or missing state, or no snapshot at all, as quiet", () => {
    expect(trayModel(snap({ state: "mystery" }), NOW).state).toBe("quiet");
    expect(trayModel(null, NOW)).toMatchObject({ state: "quiet", rows: [], counts: [] });
    expect(trayModel(undefined, NOW).title).toBe("All quiet");
  });
});

describe("trayModel copy and plurals", () => {
  it("uses the singular for one thing", () => {
    expect(trayModel(needsSnap(1), NOW)).toMatchObject({ title: "P0 needs you", sub: "1 approval" });
    const one = trayModel(snap({ state: "failing", failing: { jobs: 1, profileCount: 1, profiles: ["sentinel"] } }), NOW);
    expect(one).toMatchObject({ title: "1 job failing", failing: { title: "1 job failed in 24 h", detail: "sentinel" } });
    expect(trayModel(snap({ state: "running", running: { count: 1, rows: [] } }), NOW).title).toBe("1 working");
  });

  it("names the one agent that is working and counts two or more", () => {
    const state = (rows, count = rows.length) => snap({ state: "running", running: { count, rows } });
    const m = trayModel(state([turn(0, { label: "sentinel", ts: sec(660) })]), NOW);
    expect(m).toMatchObject({ title: "Sentinel is working", sub: "Nothing needs you" });
    expect(m.runs[0].elapsed).toBe("11m");
    expect(trayModel(state([turn(0, { label: "sentinel" }), turn(1, { label: "alpi" })]), NOW).title).toBe("2 working");
    expect(trayModel(state([turn(0, { label: "a" }), turn(1, { label: "b" }), turn(2, { label: "c" })]), NOW).title).toBe("3 working");
    expect(trayModel(state([turn(0), turn(1)]), NOW).title).toBe("Alpi is working");
  });

  it("counts the turns instead of naming an agent when the rows do not cover them all", () => {
    const m = trayModel(snap({ state: "running", running: { count: 6, rows: [0, 1, 2, 3].map((i) => turn(i, { label: "a" })) } }), NOW);
    expect(m.title).toBe("6 working");
  });

  it("sums up in the subtitle what the title does not say, then when the next job runs", () => {
    const next = { total: 4, rows: [{ id: "j", title: "Job", label: "scribe", at: new Date(NOW + 2 * 3600e3).toISOString() }] };
    const running = trayModel(snap({ state: "running", running: { count: 1, rows: [turn(0, { label: "sentinel" })] }, next }), NOW);
    expect(running.sub).toBe("Nothing needs you · next in 2h");
    const needing = trayModel(snap({ ...needsSnap(1), running: { count: 1, rows: [turn(0)] }, next }), NOW);
    expect(needing.sub).toBe("1 running · next in 2h");
    const noon = new Date(2026, 9, 27, 9, 0, 0).getTime();
    const sub = (date) => trayModel(snap({ next: { rows: [{ id: "j", title: "Job", label: "scribe", at: date.toISOString() }] } }), noon).sub;
    const evening = new Date(2026, 9, 27, 18, 0, 0);
    expect(sub(evening)).toBe(`Nothing needs you · next at ${new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(evening)}`);
    expect(sub(new Date(2026, 9, 28, 7, 0, 0))).toBe("Nothing needs you · next tomorrow");
    const thursday = new Date(2026, 9, 29, 7, 0, 0);
    expect(sub(thursday)).toBe(`Nothing needs you · next ${new Intl.DateTimeFormat(undefined, { weekday: "short" }).format(thursday)}`);
    const failing = trayModel(snap({ state: "failing", failing: { jobs: 2, profileCount: 1, profiles: ["a"] }, next }), NOW);
    expect(failing.sub).toBe("Nothing needs you · next in 2h");
  });

  it("describes a question as a question", () => {
    const rows = [need(0, { kind: "question", title: "", label: "doc", ts: sec(10) })];
    const m = trayModel(snap({ state: "needs", needs: { total: 1, approvals: 0, questions: 1, rows } }), NOW);
    expect(m).toMatchObject({ title: "Doc needs you", sub: "1 question" });
    expect(m.rows[0]).toMatchObject({ kind: "question", title: "has a question", name: "doc", meta: "question · now" });
  });

  it("leaves the names to the rows and counts the kinds in the subtitle", () => {
    const rows = [need(0, { label: "abby" }), need(1, { label: "doc" }), need(2, { label: "sentinel" })];
    const three = trayModel(snap({ state: "needs", needs: { total: 3, approvals: 3, questions: 0, rows } }), NOW);
    expect(three).toMatchObject({ title: "3 need you", sub: "3 approvals" });
    expect(three.rows.map((r) => r.name)).toEqual(["abby", "doc", "sentinel"]);
    const mixed = trayModel(snap({ state: "needs", needs: { total: 3, approvals: 2, questions: 1, rows: [need(0)] } }), NOW);
    expect(mixed.sub).toBe("2 approvals, 1 question");
    const only = trayModel(snap({ state: "needs", needs: { total: 3, approvals: 0, questions: 3, rows: [need(0)] } }), NOW);
    expect(only.sub).toBe("3 questions");
  });

  it("names two failing profiles, and a third as N more", () => {
    const three = trayModel(snap({ state: "failing", failing: { jobs: 5, profileCount: 3, profiles: ["a", "b"] } }), NOW);
    expect(three.failing.detail).toBe("a, b and 1 more");
    const four = trayModel(snap({ state: "failing", failing: { jobs: 5, profileCount: 4, profiles: ["a", "b"] } }), NOW);
    expect(four.failing.detail).toBe("a, b and 2 more");
  });

  it("falls back when the failing profiles are unknown", () => {
    expect(trayModel(snap({ state: "failing", failing: { jobs: 2, profileCount: 0, profiles: [] } }), NOW).failing).toEqual({ title: "2 jobs failed in 24 h", detail: "" });
  });

  it("falls back to the profile when a running turn has no title", () => {
    const m = trayModel(snap({ state: "running", running: { count: 1, rows: [turn(0, { title: "" })] } }), NOW);
    expect(m.runs[0].title).toBe("alpi");
  });

  it("explains an outage by its cause", () => {
    expect(trayModel(snap({ state: "offline", offline: { local: true, canStart: false, absent: true } }), NOW)).toMatchObject({ title: "alpi isn’t installed", start: false });
    expect(trayModel(snap({ state: "offline", offline: { local: true, canStart: false, absent: false } }), NOW).title).toBe("alpi isn’t running");
    expect(trayModel(snap({ state: "offline", offline: { local: false, canStart: false, absent: false } }), NOW)).toMatchObject({ title: "Can’t reach alpi", start: false });
    expect(trayModel(snap({ state: "offline" }), NOW).title).toBe("Can’t reach alpi");
    expect(trayModel(snap({ state: "connecting" }), NOW)).toMatchObject({ title: "Connecting…", busy: null });
  });

  it("never offers Start unless the snapshot can start", () => {
    expect(trayModel(snap({ state: "quiet", offline: { canStart: true } }), NOW).start).toBe(false);
  });

  it("words an update without a version", () => {
    expect(trayModel(snap({ update: { version: null, busy: true } }), NOW).update).toEqual({ text: "An update is ready", busy: true });
  });
});

describe("trayModel limits and ordering", () => {
  it("never draws more than four needs-you rows even if handed more", () => {
    const rows = Array.from({ length: 9 }, (_, i) => need(i));
    const m = trayModel(snap({ state: "needs", needs: { total: 9, approvals: 9, questions: 0, rows } }), NOW);
    expect(m.rows.map((r) => r.key)).toEqual(["r0", "r1", "r2", "r3"]);
    expect(m.more).toBe(5);
  });

  it("has no more row at exactly four, or fewer", () => {
    expect(trayModel(needsSnap(4), NOW)).toMatchObject({ more: 0 });
    expect(trayModel(needsSnap(3), NOW)).toMatchObject({ more: 0 });
  });

  it("keeps the daemon order of the rows", () => {
    const rows = [need(2), need(0), need(1)];
    const m = trayModel(snap({ state: "needs", needs: { total: 3, approvals: 3, questions: 0, rows } }), NOW);
    expect(m.rows.map((r) => r.key)).toEqual(["r2", "r0", "r1"]);
  });

  it("draws failing as a banner and running without rows as the one count line", () => {
    const m = trayModel(snap({ state: "needs", needs: { total: 1, approvals: 1, questions: 0, rows: [need(0)] }, running: { count: 2, rows: [] }, failing: { jobs: 1, profileCount: 1, profiles: ["x"] } }), NOW);
    expect(m.failing).toEqual({ title: "1 job failed in 24 h", detail: "x" });
    expect(m.counts.map((c) => c.key)).toEqual(["running"]);
  });

  it("hides rows and counts while the daemon is not reachable", () => {
    const m = trayModel(snap({ state: "offline", needs: { total: 2, approvals: 2, questions: 0, rows: [need(0)] }, running: { count: 1, rows: [] }, failing: { jobs: 1, profileCount: 1, profiles: ["x"] } }), NOW);
    expect(m).toMatchObject({ rows: [], more: 0, counts: [], failing: null });
  });

  it("tolerates garbage counts", () => {
    const m = trayModel(snap({ state: "failing", failing: { jobs: "x", profileCount: -4, profiles: [] }, running: { count: NaN, first: null } }), NOW);
    expect(m.counts).toEqual([]);
    expect(m.failing).toBeNull();
    expect(m.title).toBe("0 jobs failing");
  });
});

describe("trayModel members and the bell", () => {
  it("hides the bell for a member connection", () => {
    expect(trayModel(snap({ member: true }), NOW).bell).toBe(false);
    expect(trayModel(snap({ member: false }), NOW).bell).toBe(true);
  });

  it("labels the bell plainly with nothing unread", () => {
    expect(trayModel(snap(), NOW).bellLabel).toBe("Notifications");
  });

  it("carries the row's deeplink untouched and null when absent", () => {
    const m = trayModel(snap({ state: "needs", needs: { total: 2, approvals: 2, questions: 0, rows: [need(0), need(1, { deeplink: undefined })] } }), NOW);
    expect(m.rows[0].deeplink).toEqual({ kind: "approval", profile: "p0", id: "r0", connection_id: "c1" });
    expect(m.rows[1].deeplink).toBeNull();
  });

  it("dates a row against the clock it is given", () => {
    const rows = [need(0, { ts: sec(7200) }), need(1, { ts: sec(5) })];
    const m = trayModel(snap({ state: "needs", needs: { total: 2, approvals: 2, questions: 0, rows } }), NOW);
    expect(m.rows[0].meta).toBe("approval · 2h");
    expect(m.rows[1].meta).toBe("approval · now");
  });
});

describe("trayModel without a verdict on activity", () => {
  it("draws a neutral heading for a daemon that cannot list activity", () => {
    const m = trayModel(snap({ state: "online" }), NOW);
    expect(m).toMatchObject({ state: "online", title: "alpi", sub: "online", rows: [], counts: [], more: 0 });
    expect(`${m.title} ${m.sub}`).not.toMatch(/quiet|Nothing needs/i);
  });

  it("draws Connecting while the first activity reply is pending", () => {
    expect(trayModel(snap({ state: "connecting" }), NOW)).toMatchObject({ title: "Connecting…", sub: "Waiting for the daemon" });
  });

  it("still tells a real quiet", () => {
    expect(trayModel(snap(), NOW)).toMatchObject({ title: "All quiet", sub: "Nothing needs you" });
    expect(trayModel(snap({ next: null }), NOW)).toMatchObject({ title: "All quiet", sub: "Nothing needs you, nothing scheduled" });
  });

  it("heads a reduced snapshot by its counts alone", () => {
    expect(trayModel({ v: 1, state: "needs", counts: { needs: 3, failing: 0, running: 0 } }, NOW)).toMatchObject({
      title: "3 need you",
      sub: "Open alpi to review",
      rows: [],
      more: 0,
      counts: [{ key: "needs", icon: "clock", label: "Needs you", value: "3", danger: false }],
    });
    expect(trayModel({ v: 1, state: "needs", counts: { needs: 2, failing: 1, running: 2 } }, NOW)).toMatchObject({
      title: "2 need you",
      sub: "2 running",
      failing: { title: "1 job failed in 24 h", detail: "" },
      runs: [],
    });
    expect(trayModel({ v: 1, state: "needs", counts: { needs: 2, failing: 1, running: 2 } }, NOW).counts.map((c) => c.key)).toEqual(["needs", "running"]);
    expect(trayModel({ v: 1, state: "quiet" }, NOW)).toMatchObject({ title: "All quiet", sub: "Nothing needs you", counts: [], failing: null });
    expect(trayModel({ v: 1, state: "offline" }, NOW)).toMatchObject({ title: "Can’t reach alpi", counts: [] });
    expect(trayModel({ v: 1, state: "failing", counts: { failing: 2 } }, NOW)).toMatchObject({ title: "2 jobs failing", failing: { title: "2 jobs failed in 24 h", detail: "" } });
    expect(trayModel({ v: 1, state: "running", counts: { running: 1 } }, NOW).title).toBe("1 working");
  });
});

describe("trayModel schedule by day", () => {
  const BASE = new Date(2026, 9, 27, 12, 0, 0).getTime();
  const at = (ms) => new Date(BASE + ms).toISOString();
  const AT = at(5 * 3600e3);
  const job = (i, over = {}) => ({ id: `c/p/j${i}`, title: `Job ${i}`, label: "scribe", at: AT, source: null, shape: "llama", accent: "#14110c", deeplink: { kind: "settings", profile: "scribe", id: "schedules", connection_id: "c" }, ...over });
  const quiet = (over = {}) => snap({ next: { rows: [job(0)] }, ...over });
  const days = (m) => m.nextGroups.map((g) => [g.day, g.rows.map((r) => r.key)]);

  it("groups the next jobs under Later today, Tomorrow and the short weekday", () => {
    const tomorrow = new Date(2026, 9, 28, 7, 0, 0);
    const thursday = new Date(2026, 9, 29, 9, 0, 0);
    const rows = [job(0, { at: at(2 * 3600e3) }), job(1, { at: tomorrow.toISOString() }), job(2, { at: thursday.toISOString() })];
    const m = trayModel(quiet({ next: { rows } }), BASE);
    expect(days(m)).toEqual([["Later today", ["c/p/j0"]], ["Tomorrow", ["c/p/j1"]], [new Intl.DateTimeFormat(undefined, { weekday: "short" }).format(thursday), ["c/p/j2"]]]);
    expect(m.sub).toBe("Nothing needs you · next in 2h");
    expect(m.nextGroups[0].rows[0]).toEqual({ key: "c/p/j0", title: "Job 0", name: "scribe", connection: null, when: "in 2h", shape: "llama", accent: "#14110c", deeplink: expect.any(Object) });
    const clock = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });
    expect(m.nextGroups[1].rows[0].when).toBe(clock.format(tomorrow));
  });

  it("says the next job is due now when it is overdue or under a minute away, never next now", () => {
    expect(trayModel(quiet({ next: { rows: [job(0, { at: at(-5 * 60e3) })] } }), BASE).sub).toBe("Nothing needs you · next due now");
    expect(trayModel(quiet({ next: { rows: [job(0, { at: at(20e3) })] } }), BASE).sub).toBe("Nothing needs you · next due now");
    expect(trayModel(needsSnap(1, { next: { rows: [job(0, { at: at(-60e3) })] } }), BASE).sub).toBe("1 approval · next due now");
  });

  it("keeps two jobs of the same day in one group", () => {
    const m = trayModel(quiet({ next: { rows: [job(0, { at: at(3600e3) }), job(1, { at: at(5 * 3600e3) })] } }), BASE);
    expect(days(m)).toEqual([["Later today", ["c/p/j0", "c/p/j1"]]]);
  });

  it("counts down under six hours and shows the clock from six hours on", () => {
    const clock = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });
    const edge = new Date(BASE + 6 * 3600e3);
    const m = trayModel(quiet({ next: { rows: [job(0, { at: at(25 * 60e3) }), job(1, { at: at(6 * 3600e3 - 60e3) }), job(2, { at: edge.toISOString() })] } }), BASE);
    expect(m.nextGroups.flatMap((g) => g.rows.map((r) => r.when))).toEqual(["in 25m", "in 5h", clock.format(edge)]);
  });

  it("names the connection only when the snapshot brings one", () => {
    const m = trayModel(quiet({ next: { rows: [job(0), job(1, { source: "mirai" })] } }), BASE);
    expect(m.nextGroups[0].rows.map((r) => [r.name, r.connection])).toEqual([["scribe", null], ["scribe", "mirai"]]);
  });

  it("caps the list at three rows", () => {
    const m = trayModel(quiet({ next: { rows: [0, 1, 2, 3, 4].map((i) => job(i)) } }), BASE);
    expect(m.nextGroups.flatMap((g) => g.rows)).toHaveLength(3);
  });

  it("falls back to the title-less profile label", () => {
    expect(trayModel(quiet({ next: { rows: [job(0, { title: "" })] } }), BASE).nextGroups[0].rows[0].title).toBe("scribe");
  });

  it("says nothing is scheduled for an admin with no job", () => {
    const m = trayModel(quiet({ next: null }), BASE);
    expect(m.sub).toBe("Nothing needs you, nothing scheduled");
    expect(m.nextGroups).toEqual([]);
  });

  it("never claims nothing scheduled to a member and lists the jobs another connection brought", () => {
    expect(trayModel(snap({ member: true, next: null }), BASE).sub).toBe("Nothing needs you");
    const m = trayModel(quiet({ member: true }), BASE);
    expect(m.sub).toBe("Nothing needs you · next in 5h");
    expect(m.nextGroups).toHaveLength(1);
  });

  it("names the connection on a needs-you and a running row", () => {
    const needs = trayModel(snap({ state: "needs", needs: { total: 1, approvals: 1, questions: 0, rows: [{ id: "m/1", kind: "approval", label: "sentinel", source: "mirai", title: "t", ts: null }] } }), BASE);
    expect(needs).toMatchObject({ title: "Sentinel needs you", sub: "1 approval" });
    expect(needs.rows[0]).toMatchObject({ name: "sentinel", connection: "mirai", meta: "approval" });
    const running = trayModel(snap({ state: "running", running: { count: 1, rows: [{ id: "m/s", label: "sentinel", source: "mirai", title: "Review", ts: null }] } }), BASE);
    expect(running.runs[0]).toMatchObject({ name: "sentinel", connection: "mirai", elapsed: "" });
  });

  it("renders a snapshot without next", () => {
    expect(trayModel(snap(), BASE)).toMatchObject({ sub: "Nothing needs you", nextGroups: [] });
  });

  it("makes no claim when the daemon cannot list activity or is still loading", () => {
    expect(trayModel(quiet({ state: "online", next: null }), BASE)).toMatchObject({ title: "alpi", sub: "online", nextGroups: [] });
    expect(trayModel(quiet({ state: "connecting" }), BASE)).toMatchObject({ title: "Connecting…", nextGroups: [] });
  });

  it("keeps the schedule beside running, needs you and failing within the five-row budget", () => {
    const next = { total: 3, rows: [0, 1, 2].map((i) => job(i)) };
    const running = { count: 1, rows: [turn(0)] };
    const rowsOf = (m) => m.nextGroups.flatMap((g) => g.rows);
    const beside = trayModel(snap({ state: "running", running, next }), BASE);
    expect(beside.runs).toHaveLength(1);
    expect(rowsOf(beside)).toHaveLength(2);
    const failing = trayModel(snap({ state: "failing", failing: { jobs: 3, profileCount: 2, profiles: ["a", "b"] }, next }), BASE);
    expect(rowsOf(failing)).toHaveLength(3);
    const needing = trayModel(snap({ ...needsSnap(2), running, next }), BASE);
    expect(needing.rows.length + needing.runs.length + rowsOf(needing).length).toBeLessThanOrEqual(5);
    expect(rowsOf(needing)).toHaveLength(2);
  });

  it("counts the failing banner and every more line against the five-row budget", () => {
    const lines = (m) => m.rows.length + (m.more ? 1 : 0) + (m.failing ? 1 : 0) + m.runs.length + (m.runsMore ? 1 : 0) + m.nextGroups.flatMap((g) => g.rows).length;
    const failing = { jobs: 1, profileCount: 1, profiles: ["a"] };
    const five = trayModel(snap({ state: "failing", failing, running: { count: 5, rows: [0, 1, 2, 3, 4].map((i) => turn(i)) } }), BASE);
    expect([five.runs.length, five.runsMore, lines(five)]).toEqual([3, 2, 5]);
    const four = trayModel(snap({ state: "failing", failing, running: { count: 4, rows: [0, 1, 2, 3].map((i) => turn(i)) } }), BASE);
    expect([four.runs.length, four.runsMore, lines(four)]).toEqual([4, 0, 5]);
    const alone = trayModel(snap({ state: "running", running: { count: 5, rows: [0, 1, 2, 3, 4].map((i) => turn(i)) } }), BASE);
    expect([alone.runs.length, alone.runsMore, lines(alone)]).toEqual([4, 1, 5]);
    const needing = trayModel(needsSnap(5, { failing }), BASE);
    expect([needing.rows.length, needing.more, lines(needing)]).toEqual([3, 2, 5]);
    const next = { total: 3, rows: [0, 1, 2].map((i) => job(i)) };
    const crowded = trayModel(snap({ state: "failing", failing, running: { count: 3, rows: [0, 1].map((i) => turn(i)) }, next }), BASE);
    expect(lines(crowded)).toBeLessThanOrEqual(5);
  });

  it("hides the schedule when needs you fills the popover", () => {
    const next = { total: 3, rows: [job(0)] };
    const m = trayModel(snap({ ...needsSnap(3), running: { count: 2, rows: [turn(0), turn(1)] }, next }), BASE);
    expect(m.nextGroups).toEqual([]);
    expect(m.counts.map((c) => c.key)).toEqual(["running"]);
  });

  it("hides the schedule while the daemon is not reachable", () => {
    for (const state of ["offline", "starting", "connecting"]) {
      expect(trayModel(quiet({ state }), BASE).nextGroups, state).toEqual([]);
    }
  });
});
