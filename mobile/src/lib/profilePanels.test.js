import { describe, expect, it } from "vitest";
import { describeTimeout, describeWhen } from "../../../common/schedule.mjs";
import { entryNote, memoryEntries } from "../../../common/memoryEntries.mjs";
import { skillFileIcon } from "../../../common/fileKind.mjs";

describe("schedule wording", () => {
  it("says when a cron job runs in words and keeps the cron when it cannot", () => {
    expect(describeWhen({ kind: "cron", expression: "0 6 * * 1" })).toBe("every Monday at 06:00");
    expect(describeWhen({ kind: "cron", expression: "30 7 * * *" })).toBe("every day at 07:30");
    expect(describeWhen({ kind: "cron", expression: "0 9 * * 1-5" })).toBe("every weekday at 09:00");
    expect(describeWhen({ kind: "cron", expression: "0 9 * * 0,6" })).toBe("every weekend day at 09:00");
    expect(describeWhen({ kind: "cron", expression: "0 9 * * 1,3" })).toBe("every Mon, Wed at 09:00");
    expect(describeWhen({ kind: "cron", expression: "0 9 1 * *" })).toBe("on day 1 of every month at 09:00");
    expect(describeWhen({ kind: "cron", expression: "*/15 * * * *" })).toBe("every 15 minutes");
    expect(describeWhen({ kind: "cron", expression: "0 */3 * * *" })).toBe("every 3 hours");
    expect(describeWhen({ kind: "cron", expression: "5 4 * 6 *" })).toBe("cron 5 4 * 6 *");
  });

  it("falls back to the cron rather than word a schedule wrongly", () => {
    expect(describeWhen({ kind: "cron", expression: "0 9 * * 6-0" })).toBe("cron 0 9 * * 6-0");
    expect(describeWhen({ kind: "cron", expression: "0 */7 * * *" })).toBe("cron 0 */7 * * *");
    expect(describeWhen({ kind: "cron", expression: "*/45 * * * *" })).toBe("cron */45 * * * *");
    expect(describeWhen({ kind: "cron", expression: "5 */2 * * *" })).toBe("every 2 hours at :05");
    expect(describeWhen({ kind: "cron", expression: "*/1 * * * *" })).toBe("every minute");
    expect(describeWhen({ kind: "cron", expression: "0 9 * * 5-7" })).toBe("every Fri, Sat, Sun at 09:00");
  });

  it("names the daemon's zone when it is not the viewer's, and reads a zoned one-off in local time", () => {
    const job = { kind: "cron", expression: "0 9 * * *", next_fire: "2026-10-05T09:00:00+00:00" };
    expect(describeWhen(job, 120)).toBe("every day at 09:00 (UTC)");
    expect(describeWhen({ ...job, next_fire: "2026-10-05T09:00:00+02:00" }, 120)).toBe("every day at 09:00");
    expect(describeWhen({ kind: "once", run_at: "2026-10-05T09:00:00Z" }, 120)).toBe("once, Mon 5 Oct at 11:00");
    expect(describeWhen({ kind: "once", run_at: "2026-10-10T09:00:00", next_fire: "2026-10-10T09:00:00-04:00" }, 120)).toBe("once, Sat 10 Oct at 09:00 (UTC-04:00)");
  });

  it("words one-off and inactivity jobs and the run timeout", () => {
    expect(describeWhen({ kind: "once", run_at: "2026-10-10T09:00:00+02:00" }, 120)).toBe("once, Sat 10 Oct at 09:00");
    expect(describeWhen({ kind: "inactivity", after_hours: 168 })).toBe("after 7 days without a message");
    expect(describeWhen({ kind: "inactivity", after_hours: 5 })).toBe("after 5 hours without a message");
    expect(describeTimeout({ run_timeout: 1200 })).toBe("20 min timeout");
    expect(describeTimeout({ run_timeout: null })).toBeNull();
  });
});

describe("memory entries", () => {
  it("splits on § and reads captured, reinforced and confidence from alpi-meta", () => {
    const raw = "One.\n<!-- alpi-meta conf=normal captured=2026-09-28 reinforced=3 -->\n§\nTwo.\n§\n\n";
    const entries = memoryEntries(raw);
    expect(entries.map((e) => e.text)).toEqual(["One.", "Two."]);
    expect(entries[0]).toMatchObject({ captured: "2026-09-28", reinforced: 3, confidence: "normal" });
    expect(entryNote(entries[0])).toBe("captured 2026-09-28 · reinforced ×3");
    expect(entryNote(entries[1])).toBe("");
    expect(memoryEntries("")).toEqual([]);
  });

});

describe("skill file icons", () => {
  it("gives a database its own icon and code its own", () => {
    expect(skillFileIcon({ name: "db.sqlite", kind: "file" })).toBe("database");
    expect(skillFileIcon({ name: "fields.yaml", kind: "file" })).toBe("file-code");
    expect(skillFileIcon({ name: "notes.md", kind: "file" })).toBe("file-text");
    expect(skillFileIcon({ name: "secrets", kind: "dir", locked: true })).toBe("lock");
    expect(skillFileIcon({ path: "secrets/", name: "secrets", kind: "locked-dir", locked: true })).toBe("lock");
  });
});
