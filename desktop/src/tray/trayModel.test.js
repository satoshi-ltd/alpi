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
  fold: "alpaca",
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

const turn = (i, over = {}) => ({ id: `t${i}`, profile: "alpi", label: "alpi", title: `Turn ${i}`, ts: NOW / 1000 - 120, fold: "llama", accent: "#14110c", deeplink: { kind: "chat", profile: "alpi", id: `s${i}`, connection_id: "c" }, ...over });

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
    expect(m).toMatchObject({ state: "quiet", title: "All quiet", sub: "Nothing needs you · online", rows: [], more: 0, counts: [], busy: null, start: false, update: null });
  });

  it("draws Needs you with the first request spelled out and the counts below", () => {
    const m = trayModel(
      needsSnap(2, { failing: { jobs: 3, profileCount: 2, profiles: ["sentinel", "clonara"] }, running: { count: 2, rows: [] }, unread: 1 }),
      NOW,
    );
    expect(m.title).toBe("2 need you");
    expect(m.sub).toBe("p0 is waiting for an approval");
    expect(m.rows).toHaveLength(2);
    expect(m.rows[0]).toMatchObject({ key: "r0", kind: "approval", title: "wants to run a command", sub: "p0 · approval · 2m ago" });
    expect(m.counts.map((c) => [c.key, c.label, c.value, c.danger])).toEqual([
      ["failing", "Failing jobs", "3 in 2 profiles", true],
      ["running", "Running", "2", false],
    ]);
    expect(m.unread).toBe(1);
    expect(m.bellLabel).toBe("Notifications · 1 unread");
  });

  it("lists the running turns as rows with their fold and elapsed time", () => {
    const m = trayModel(snap({ state: "running", running: { count: 2, rows: [turn(0), turn(1, { ts: null })] } }), NOW);
    expect(m.title).toBe("2 running");
    expect(m.sub).toBe("Working now");
    expect(m.runs).toEqual([
      { key: "t0", title: "Turn 0", sub: "alpi · running", elapsed: "2m", fold: "llama", accent: "#14110c", deeplink: { kind: "chat", profile: "alpi", id: "s0", connection_id: "c" } },
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

  it("keeps the Running count line below needs you and falls back to it without rows", () => {
    const needing = trayModel(snap({ ...needsSnap(1), running: { count: 2, rows: [turn(0)] } }), NOW);
    expect(needing.runs).toEqual([]);
    expect(needing.counts).toEqual([{ key: "running", icon: "activity", label: "Running", value: "2", danger: false }]);
    expect(trayModel(snap({ state: "running", running: { count: 2, rows: [] } }), NOW).counts).toHaveLength(1);
  });

  it("draws Failing jobs with the profiles and the Activity window", () => {
    const m = trayModel(snap({ state: "failing", failing: { jobs: 3, profileCount: 2, profiles: ["sentinel", "clonara"] } }), NOW);
    expect(m.title).toBe("3 jobs failing");
    expect(m.sub).toBe("sentinel and clonara · last 24 h");
    expect(m.counts[0].value).toBe("3 in 2 profiles");
  });

  it("draws a stopped daemon with its one action", () => {
    const m = trayModel(snap({ state: "offline", offline: { local: true, canStart: true, absent: false } }), NOW);
    expect(m).toMatchObject({ title: "alpi is installed but not running", sub: "Start it on this computer.", start: true, rows: [], counts: [] });
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
    expect(trayModel(needsSnap(1), NOW).title).toBe("1 needs you");
    expect(trayModel(snap({ state: "failing", failing: { jobs: 1, profileCount: 1, profiles: ["sentinel"] } }), NOW)).toMatchObject({
      title: "1 job failing",
      sub: "sentinel · last 24 h",
    });
    const one = trayModel(snap({ state: "failing", failing: { jobs: 1, profileCount: 1, profiles: ["sentinel"] } }), NOW);
    expect(one.counts[0].value).toBe("1 in 1 profile");
    expect(trayModel(snap({ state: "running", running: { count: 1, rows: [] } }), NOW).title).toBe("1 running");
  });

  it("describes a question as a question", () => {
    const rows = [need(0, { kind: "question", title: "", label: "doc", ts: sec(10) })];
    const m = trayModel(snap({ state: "needs", needs: { total: 1, approvals: 0, questions: 1, rows } }), NOW);
    expect(m.sub).toBe("doc has a question");
    expect(m.rows[0]).toMatchObject({ kind: "question", title: "has a question", sub: "doc · question · just now" });
  });

  it("counts questions alone in the singular and plural", () => {
    const one = trayModel(snap({ state: "needs", needs: { total: 3, approvals: 2, questions: 1, rows: [need(0)] } }), NOW);
    expect(one.sub).toBe("2 approvals, 1 question");
    const only = trayModel(snap({ state: "needs", needs: { total: 3, approvals: 0, questions: 3, rows: [need(0)] } }), NOW);
    expect(only.sub).toBe("3 questions");
  });

  it("names two failing profiles, and a third as N more", () => {
    const three = trayModel(snap({ state: "failing", failing: { jobs: 5, profileCount: 3, profiles: ["a", "b"] } }), NOW);
    expect(three.sub).toBe("a, b and 1 more · last 24 h");
    const four = trayModel(snap({ state: "failing", failing: { jobs: 5, profileCount: 4, profiles: ["a", "b"] } }), NOW);
    expect(four.sub).toBe("a, b and 2 more · last 24 h");
  });

  it("falls back when the failing profiles are unknown", () => {
    expect(trayModel(snap({ state: "failing", failing: { jobs: 2, profileCount: 0, profiles: [] } }), NOW).sub).toBe("Last 24 h");
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

  it("lists failing before running", () => {
    const m = trayModel(snap({ state: "needs", needs: { total: 1, approvals: 1, questions: 0, rows: [need(0)] }, running: { count: 2, rows: [] }, failing: { jobs: 1, profileCount: 1, profiles: ["x"] } }), NOW);
    expect(m.counts.map((c) => c.key)).toEqual(["failing", "running"]);
  });

  it("hides rows and counts while the daemon is not reachable", () => {
    const m = trayModel(snap({ state: "offline", needs: { total: 2, approvals: 2, questions: 0, rows: [need(0)] }, running: { count: 1, rows: [] }, failing: { jobs: 1, profileCount: 1, profiles: ["x"] } }), NOW);
    expect(m).toMatchObject({ rows: [], more: 0, counts: [] });
  });

  it("tolerates garbage counts", () => {
    const m = trayModel(snap({ state: "failing", failing: { jobs: "x", profileCount: -4, profiles: [] }, running: { count: NaN, first: null } }), NOW);
    expect(m.counts).toEqual([]);
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
    expect(m.rows[0].sub).toContain("2h ago");
    expect(m.rows[1].sub).toContain("just now");
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
    expect(trayModel(snap(), NOW)).toMatchObject({ title: "All quiet", sub: "Nothing needs you · online" });
  });

  it("heads a reduced snapshot by its counts alone", () => {
    expect(trayModel({ v: 1, state: "needs", counts: { needs: 3, failing: 0, running: 0 } }, NOW)).toMatchObject({ title: "3 need you", rows: [], more: 3 });
    expect(trayModel({ v: 1, state: "failing", counts: { failing: 2 } }, NOW)).toMatchObject({ title: "2 jobs failing" });
    expect(trayModel({ v: 1, state: "running", counts: { running: 1 } }, NOW).title).toBe("1 running");
  });
});

describe("trayModel quiet Next line", () => {
  const AT = new Date(NOW + 5 * 3600e3).toISOString();
  const job = (i, over = {}) => ({ id: `c/p/j${i}`, title: `Job ${i}`, label: "scribe", at: AT, source: null, fold: "llama", accent: "#14110c", deeplink: { kind: "settings", profile: "scribe", id: "schedules", connection_id: "c" }, ...over });
  const quiet = (over = {}) => snap({ next: { rows: [job(0)] }, ...over });

  it("lists the next jobs under a Coming up heading", () => {
    const m = trayModel(quiet({ next: { rows: [job(0), job(1, { source: "mirai" })] } }), NOW);
    expect(m.title).toBe("All quiet");
    expect(m.sub).toBe("Coming up");
    expect(m.nextRows).toEqual([
      { key: "c/p/j0", title: "Job 0", sub: "scribe", when: expect.any(String), fold: "llama", accent: "#14110c", deeplink: expect.any(Object) },
      expect.objectContaining({ key: "c/p/j1", sub: "scribe · mirai" }),
    ]);
  });

  it("caps the list at three rows", () => {
    expect(trayModel(quiet({ next: { rows: [0, 1, 2, 3, 4].map((i) => job(i)) } }), NOW).nextRows).toHaveLength(3);
  });

  it("falls back to the title-less profile label", () => {
    expect(trayModel(quiet({ next: { rows: [job(0, { title: "" })] } }), NOW).nextRows[0].title).toBe("scribe");
  });

  it("says Nothing scheduled for an admin with no job", () => {
    const m = trayModel(quiet({ next: null }), NOW);
    expect(m.sub).toBe("Nothing scheduled");
    expect(m.nextRows).toEqual([]);
  });

  it("keeps the neutral line for a member, even if a next slipped in", () => {
    const m = trayModel(quiet({ member: true }), NOW);
    expect(m.sub).toBe("Nothing needs you · online");
    expect(m.nextRows).toEqual([]);
  });

  it("renders today's popover for a snapshot without next", () => {
    expect(trayModel(snap(), NOW)).toMatchObject({ sub: "Nothing needs you · online", nextRows: [] });
  });

  it("makes no claim when the daemon cannot list activity or is still loading", () => {
    expect(trayModel(quiet({ state: "online", next: null }), NOW)).toMatchObject({ title: "alpi", sub: "online", nextRows: [] });
    expect(trayModel(quiet({ state: "connecting" }), NOW)).toMatchObject({ title: "Connecting…", nextRows: [] });
  });

  it("shows the line in the quiet state only", () => {
    for (const state of ["needs", "failing", "running", "offline", "starting"]) {
      expect(trayModel(quiet({ state }), NOW).nextRows, state).toEqual([]);
    }
  });
});
