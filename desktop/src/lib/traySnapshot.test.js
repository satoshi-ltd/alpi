import { describe, expect, it } from "vitest";
import { buildTraySnapshot, clip, trayLink } from "./traySnapshot.js";

const NOW = Date.UTC(2026, 9, 27, 12, 0, 0);
const sec = (agoSeconds) => (NOW - agoSeconds * 1000) / 1000;
const online = { id: "local", kind: "local", status: "online" };

const activity = {
  needs_you: [
    { request_id: "a1", kind: "approval", profile: "abby", title: "wants to run a command", ts: sec(120) },
    { request_id: "q1", kind: "clarification", profile: "doc", title: "Which lab?", ts: sec(5) },
  ],
  running: [{ profile: "default", title: "Summarize deploys" }, { profile: "doc", name: "Daily brief" }],
  scheduled: [
    { profile: "sentinel", job_id: "j1", title: "scan", last_run_status: "error", last_run_at: sec(3600) },
    { profile: "clonara", job_id: "j2", title: "sync", last_run_status: "error", last_run_at: sec(7200) },
    { profile: "clonara", job_id: "j3", title: "old", last_run_status: "error", last_run_at: sec(3 * 86400) },
  ],
};

describe("trayLink", () => {
  it("reads the connection and the local daemon", () => {
    expect(trayLink({ connection: null })).toBe("connecting");
    expect(trayLink({ connection: online })).toBe("online");
    expect(trayLink({ connection: { kind: "local", status: "probing" } })).toBe("connecting");
    expect(trayLink({ connection: { kind: "local", status: "unknown" } })).toBe("connecting");
    expect(trayLink({ connection: { kind: "local" } })).toBe("connecting");
    expect(trayLink({ connection: { kind: "local", status: "offline" }, daemon: { phase: "starting" } })).toBe("starting");
    expect(trayLink({ connection: { kind: "local", status: "offline" }, daemon: { phase: "installing" } })).toBe("starting");
    expect(trayLink({ connection: { kind: "local", status: "offline" }, daemon: { phase: "idle", launched: true } })).toBe("starting");
    expect(trayLink({ connection: { kind: "local", status: "offline" }, daemon: { phase: "idle", state: "stopped" } })).toBe("offline");
    expect(trayLink({ connection: { kind: "remote", status: "offline" }, daemon: { phase: "starting" } })).toBe("offline");
    for (const status of ["disabled", "auth-failed", "rate-limited"]) {
      expect(trayLink({ connection: { kind: "remote", status } })).toBe("offline");
    }
  });
});

describe("buildTraySnapshot next", () => {
  const future = (secs) => sec(-secs);
  const sched = (over) => ({ profile: "doc", job_id: "j", title: "Daily brief", next_fire: new Date(future(3600) * 1000).toISOString(), ...over });
  const quiet = (scheduled) => ({ connection: online, activity: { needs_you: [], running: [], scheduled }, nowMs: NOW });

  it("lists the earliest upcoming jobs first with an ISO time", () => {
    const early = sched({ job_id: "a", title: "Early", next_fire: new Date(future(600) * 1000).toISOString() });
    const late = sched({ job_id: "b", title: "Late", next_fire: new Date(future(7200) * 1000).toISOString() });
    const s = buildTraySnapshot(quiet([late, early]));
    expect(s.next.rows.map((r) => r.title)).toEqual(["Early", "Late"]);
    expect(s.next.rows[0]).toMatchObject({ at: new Date(future(600) * 1000).toISOString(), source: null, deeplink: { kind: "settings", profile: "doc", id: "schedules", connection_id: "local" } });
  });

  it("keeps three rows across every connection and names the one each comes from", () => {
    const at = (secs) => new Date(future(secs) * 1000).toISOString();
    const own = [sched({ job_id: "h1", title: "Here", next_fire: at(7200) }), sched({ job_id: "h2", title: "Here 2", next_fire: at(9000) })];
    const there = [sched({ job_id: "t1", title: "There", next_fire: at(600) }), sched({ job_id: "t2", title: "There 2", next_fire: at(1200) })];
    const s = buildTraySnapshot({ ...quiet(own), connection: { ...online, name: "casa" }, otherSchedules: [{ id: "mirai", name: "mirai", scheduled: there }] });
    expect(s.next.rows.map((r) => [r.title, r.source])).toEqual([["There", "mirai"], ["There 2", "mirai"], ["Here", "casa"]]);
    expect(s.next.rows[0].deeplink.connection_id).toBe("mirai");
    expect(buildTraySnapshot({ ...quiet([]), otherSchedules: [{ id: "mirai", name: "mirai", scheduled: there }] }).next.rows[0].title).toBe("There");
    expect(buildTraySnapshot({ ...quiet([]), otherSchedules: [{ id: "mirai", name: "mirai", scheduled: [] }] }).next).toBeNull();
  });

  it("draws each row with the fold and accent of its own connection", () => {
    const at = (secs) => new Date(future(secs) * 1000).toISOString();
    const own = [sched({ job_id: "h", title: "Here", profile: "doc", next_fire: at(7200) })];
    const there = [sched({ job_id: "t", title: "There", profile: "sentinel", next_fire: at(600) })];
    const s = buildTraySnapshot({
      ...quiet(own),
      connection: { ...online, name: "casa" },
      foldByProfile: { doc: "owl" },
      accentByProfile: { doc: "#aa0000" },
      otherSchedules: [{ id: "mirai", name: "mirai", scheduled: there, folds: { sentinel: "diamond" }, accents: { sentinel: "#00aa00" } }],
    });
    expect(s.next.rows.map((r) => [r.title, r.fold, r.accent])).toEqual([["There", "diamond", "#00aa00"], ["Here", "owl", "#aa0000"]]);
  });

  it("names no connection while only one contributes jobs", () => {
    const own = sched({ title: "Here" });
    const s = buildTraySnapshot({ ...quiet([own]), connection: { ...online, name: "casa" }, otherSchedules: [{ id: "mirai", name: "mirai", scheduled: [] }] });
    expect(s.next.rows.map((r) => r.source)).toEqual([null]);
  });

  it("does not list the active connection twice while its own rows are still in the other list", () => {
    const own = sched({ title: "Here" });
    const s = buildTraySnapshot({ ...quiet([own]), connection: { ...online, name: "casa" }, otherSchedules: [{ id: "local", name: "casa", scheduled: [own] }] });
    expect(s.next.rows).toHaveLength(1);
  });

  it("ignores another connection's job that is already past", () => {
    const past = sched({ next_fire: new Date(future(-60) * 1000).toISOString() });
    expect(buildTraySnapshot({ ...quiet([]), otherSchedules: [{ id: "m", name: "m", scheduled: [past] }] }).next).toBeNull();
  });

  it("falls back to the job id and cuts a long title at 200 characters", () => {
    expect(buildTraySnapshot(quiet([sched({ title: "" })])).next.rows[0].title).toBe("j");
    const s = buildTraySnapshot(quiet([sched({ title: "t".repeat(5000) })]));
    expect(s.next.rows[0].title.length).toBe(200);
    expect(s.next.rows[0].title.endsWith("…")).toBe(true);
  });

  it("is null with no scheduled job, and for a member whatever the daemon lists", () => {
    expect(buildTraySnapshot(quiet([])).next).toBeNull();
    expect(buildTraySnapshot({ ...quiet([sched({})]), member: true }).next).toBeNull();
  });

  it("is null while loading and when the verb is missing", () => {
    expect(buildTraySnapshot({ connection: online, activity: null }).next).toBeNull();
    expect(buildTraySnapshot({ ...quiet([sched({})]), activitySupported: false }).next).toBeNull();
  });

  it("stays on version 1 and carries no ask", () => {
    const s = buildTraySnapshot(quiet([]));
    expect(s.v).toBe(1);
    expect(s).not.toHaveProperty("ask");
  });
});

describe("buildTraySnapshot", () => {
  const base = { connection: online, activity, foldByProfile: { abby: "alpaca" }, accentByProfile: { abby: "#df4b9d" }, nowMs: NOW };

  it("counts what Activity counts and names the heading state", () => {
    const s = buildTraySnapshot({ ...base, unread: 3 });
    expect(s.state).toBe("needs");
    expect(s.counts).toEqual({ needs: 2, failing: 2, running: 2 });
    expect(s.needs).toMatchObject({ total: 2, approvals: 1, questions: 1 });
    expect(s.failing).toEqual({ jobs: 2, profileCount: 2, profiles: ["sentinel", "clonara"] });
    expect(s.running.count).toBe(2);
    expect(s.running.rows.map((r) => [r.label, r.title, r.deeplink])).toEqual([
      ["alpi", "Summarize deploys", { kind: "profile", profile: "default", id: "default", connection_id: "local" }],
      ["doc", "Daily brief", { kind: "profile", profile: "doc", id: "doc", connection_id: "local" }],
    ]);
    expect(s.unread).toBe(3);
  });

  it("builds a Review deeplink in the shape the notification listener resolves", () => {
    const [approval, question] = buildTraySnapshot(base).needs.rows;
    expect(approval).toMatchObject({ id: "a1", kind: "approval", label: "abby", fold: "alpaca", accent: "#df4b9d" });
    expect(approval.deeplink).toEqual({ kind: "approval", profile: "abby", id: "a1", connection_id: "local" });
    expect(question).toMatchObject({ kind: "question", fold: null, accent: null });
    expect(question.deeplink).toEqual({ kind: "clarification", profile: "doc", id: "q1", connection_id: "local" });
  });

  it("sends at most four rows but the real total", () => {
    const many = { needs_you: Array.from({ length: 9 }, (_, i) => ({ request_id: `r${i}`, kind: "approval", profile: "abby", ts: sec(i) })) };
    const s = buildTraySnapshot({ ...base, activity: many });
    expect(s.needs.rows).toHaveLength(4);
    expect(s.needs.total).toBe(9);
    expect(s.counts.needs).toBe(9);
  });

  it("shows no scheduled jobs and no unread for a member", () => {
    const s = buildTraySnapshot({ ...base, member: true, unread: 5 });
    expect(s.member).toBe(true);
    expect(s.counts.failing).toBe(0);
    expect(s.failing).toEqual({ jobs: 0, profileCount: 0, profiles: [] });
    expect(s.unread).toBe(0);
    const quiet = buildTraySnapshot({ ...base, member: true, activity: { scheduled: activity.scheduled } });
    expect(quiet.state).toBe("quiet");
  });

  it("is really quiet only once the activity has loaded empty", () => {
    const empty = { needs_you: [], running: [], scheduled: [] };
    expect(buildTraySnapshot({ connection: online, activity: empty }).state).toBe("quiet");
  });

  it("opens a running chat turn by its session", () => {
    const s = buildTraySnapshot({ connection: online, activity: { needs_you: [], running: [{ kind: "turn", profile: "abby", session_id: "s9", title: "x", started_at: 100 }], scheduled: [] }, foldByProfile: { abby: "llama" }, nowMs: NOW });
    expect(s.running.rows[0]).toMatchObject({ profile: "abby", fold: "llama", ts: 100, deeplink: { kind: "chat", profile: "abby", id: "s9", connection_id: "local" } });
  });

  it("opens a workgroup pipeline row by its workgroup and keeps repeated runs distinct", () => {
    const run = { kind: "turn", profile: "sentinel", job_id: "j1", title: "Sweep" };
    const s = buildTraySnapshot({ connection: online, activity: { needs_you: [], running: [{ kind: "workgroup", profile: "hub", workgroup_id: "wg1", name: "Release" }, run, run], scheduled: [] }, nowMs: NOW });
    expect(s.running.rows[0].deeplink).toEqual({ kind: "workgroup", profile: "hub", id: "wg1", connection_id: "local" });
    expect(new Set(s.running.rows.map((r) => r.id)).size).toBe(3);
    expect(s.running.rows[1].id).toBe("sentinel/j1");
  });

  it("does not announce quiet while the first activity reply is pending", () => {
    const s = buildTraySnapshot({ connection: online, activity: null });
    expect(s.state).toBe("connecting");
    expect(s.counts).toEqual({ needs: 0, failing: 0, running: 0 });
  });

  it("makes no claim about what needs you on a daemon without host.activity.list", () => {
    const s = buildTraySnapshot({ ...base, activity: null, activitySupported: false });
    expect(s.state).toBe("online");
    expect(s.counts).toEqual({ needs: 0, failing: 0, running: 0 });
    expect(s.needs.rows).toEqual([]);
    expect(buildTraySnapshot({ ...base, activitySupported: false }).state).toBe("online");
  });

  it("keeps an offline link offline whatever the activity says", () => {
    expect(buildTraySnapshot({ connection: { kind: "remote", status: "offline" }, activity: null, activitySupported: false }).state).toBe("offline");
  });

  it("keeps a 100 KB command well under the cap Rust enforces", () => {
    const huge = "x".repeat(100 * 1024);
    const many = {
      needs_you: Array.from({ length: 9 }, (_, i) => ({ request_id: `r${i}`, kind: "approval", profile: "abby", title: huge, ts: sec(i) })),
      running: [{ profile: "abby", title: huge }],
      scheduled: [],
    };
    const s = buildTraySnapshot({ ...base, activity: many, update: { version: "v".repeat(500), busy: false } });
    expect(JSON.stringify(s).length).toBeLessThan(8 * 1024);
    expect(s.needs.rows[0].title.length).toBe(200);
    expect(s.needs.rows[0].title.endsWith("…")).toBe(true);
    expect(s.running.rows[0].title.length).toBe(200);
    expect(s.update.version.length).toBe(32);
  });

  it("leaves short text alone", () => {
    expect(buildTraySnapshot(base).needs.rows[0].title).toBe("wants to run a command");
  });

  it("ranks failing over running when nothing needs you", () => {
    expect(buildTraySnapshot({ ...base, activity: { ...activity, needs_you: [] } }).state).toBe("failing");
    expect(buildTraySnapshot({ ...base, activity: { running: activity.running } }).state).toBe("running");
  });

  it("drops a job that is running again from the failing count", () => {
    const s = buildTraySnapshot({ ...base, activity: { running: [{ profile: "sentinel", job_id: "j1" }], scheduled: activity.scheduled } });
    expect(s.failing.jobs).toBe(1);
  });

  it("ignores activity while the daemon is not online", () => {
    const s = buildTraySnapshot({ ...base, connection: { id: "local", kind: "local", status: "offline" }, daemon: { state: "stopped", phase: "idle" } });
    expect(s.state).toBe("offline");
    expect(s.counts).toEqual({ needs: 0, failing: 0, running: 0 });
    expect(s.offline).toEqual({ local: true, canStart: true, absent: false });
  });

  it("tells a stopped daemon from an absent one and from a remote", () => {
    const off = (connection, daemon) => buildTraySnapshot({ connection, daemon }).offline;
    expect(off({ kind: "local", status: "offline" }, { state: "absent", phase: "idle" })).toEqual({ local: true, canStart: false, absent: true });
    expect(off({ kind: "local", status: "offline" }, { state: "unsupported", phase: "idle" })).toEqual({ local: true, canStart: false, absent: true });
    expect(off({ kind: "remote", status: "offline" }, { state: "stopped" })).toEqual({ local: false, canStart: false, absent: false });
  });

  it("reports starting while the local daemon launches", () => {
    const s = buildTraySnapshot({ connection: { kind: "local", status: "offline" }, daemon: { phase: "starting" } });
    expect(s.state).toBe("starting");
    expect(s.offline).toBeNull();
  });

  it("carries an update and clamps the unread count", () => {
    expect(buildTraySnapshot({ ...base, update: { version: "0.9.3", busy: true } }).update).toEqual({ version: "0.9.3", busy: true });
    expect(buildTraySnapshot({ ...base, update: { busy: false } }).update).toEqual({ version: null, busy: false });
    expect(buildTraySnapshot(base).update).toBeNull();
    expect(buildTraySnapshot({ ...base, unread: -2 }).unread).toBe(0);
    expect(buildTraySnapshot({ ...base, unread: "x" }).unread).toBe(0);
  });

  it("serialises identically for the same inputs, so identical pushes can be skipped", () => {
    expect(JSON.stringify(buildTraySnapshot(base))).toBe(JSON.stringify(buildTraySnapshot({ ...base })));
  });
});

describe("clip never exceeds the cap in UTF-16 units and never splits a surrogate pair", () => {
  const wellFormed = (text) => !/[\ud800-\udbff](?![\udc00-\udfff])|(?<![\ud800-\udbff])[\udc00-\udfff]/.test(text);

  it("keeps BMP text to exactly the cap with an ellipsis", () => {
    const out = clip("é".repeat(500));
    expect(out).toHaveLength(200);
    expect(out.endsWith("…")).toBe(true);
  });

  it("leaves text at or under the cap alone", () => {
    expect(clip("short")).toBe("short");
    expect(clip("a".repeat(200))).toBe("a".repeat(200));
    expect(clip("😀".repeat(100))).toBe("😀".repeat(100));
    expect(clip(null)).toBe("");
  });

  it("steps back when an emoji straddles the cut", () => {
    const out = clip(`${"a".repeat(198)}😀😀`);
    expect(wellFormed(out)).toBe(true);
    expect(out).toBe(`${"a".repeat(198)}…`);
    expect(out.length).toBeLessThanOrEqual(200);
  });

  it("cuts a title of only emoji on a whole emoji", () => {
    const out = clip("😀".repeat(500));
    expect(wellFormed(out)).toBe(true);
    expect(out.length).toBeLessThanOrEqual(200);
    expect(out.endsWith("…")).toBe(true);
    expect(Array.from(out).slice(0, -1).every((c) => c === "😀")).toBe(true);
  });

  it("applies the same rule to the version cap", () => {
    const out = clip(`${"v".repeat(30)}😀😀`, 32);
    expect(wellFormed(out)).toBe(true);
    expect(out.length).toBeLessThanOrEqual(32);
  });

  it("produces a whole snapshot that round-trips as well-formed JSON", () => {
    const tail = `${"a".repeat(198)}😀😀`;
    const activity = {
      needs_you: [{ request_id: "r", kind: "approval", profile: "abby", title: tail, ts: 1 }],
      running: [{ profile: "abby", title: "😀".repeat(500) }],
      scheduled: [{ profile: "doc", job_id: "j", title: tail, next_fire: new Date(Date.now() + 3600e3).toISOString() }],
    };
    const quiet = { needs_you: [], running: [], scheduled: activity.scheduled };
    for (const act of [activity, quiet]) {
      const s = buildTraySnapshot({ connection: online, activity: act, update: { version: `${"v".repeat(31)}😀😀`, busy: false }, askProfile: undefined });
      const json = JSON.stringify(s);
      expect(wellFormed(json)).toBe(true);
      if (typeof json.isWellFormed === "function") expect(json.isWellFormed()).toBe(true);
      expect(JSON.parse(json)).toEqual(s);
    }
  });
});
