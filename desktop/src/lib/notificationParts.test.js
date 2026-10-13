import { describe, it, expect } from "vitest";
import { SUMMARY_CASES } from "../../../common/notificationSummary.fixtures.mjs";
import { deriveSummary, legacyTitle, notificationTitle, SUMMARY_MAX } from "../../../common/notificationSummary.mjs";
import { notificationParts } from "../../../common/notificationParts.mjs";
import { notificationStamp, notificationTime } from "../../../common/notificationTime.mjs";

const CLOCK = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });
const WEEKDAY = new Intl.DateTimeFormat(undefined, { weekday: "short" });
const NOW = new Date(2026, 9, 11, 12, 0).getTime();
const at = (days, hour, minute = 0) => new Date(2026, 9, 11 - days, hour, minute).getTime() / 1000;

describe("deriveSummary", () => {
  it.each(SUMMARY_CASES.map(([body, summary]) => [body.slice(0, 32) || "empty", body, summary]))("matches the daemon on %s", (_, body, summary) => {
    expect(deriveSummary(body)).toBe(summary);
  });

  it("never exceeds the cap or ends on a colon", () => {
    for (const [body] of SUMMARY_CASES) {
      const summary = deriveSummary(body);
      expect(Array.from(summary).length).toBeLessThanOrEqual(SUMMARY_MAX);
      expect(summary.endsWith(":")).toBe(false);
    }
  });

  it("keeps hyphens, underscores and dates that the old preview stripped", () => {
    expect(deriveSummary("checkout-confirm on 2026-10-11 for snake_case_id."))
      .toBe("checkout-confirm on 2026-10-11 for snake_case_id.");
  });
});

describe("notificationTitle", () => {
  it("shows a stored title as written, decorative emoji aside, so reading it twice loses nothing", () => {
    expect(notificationTitle("Fix **kwargs** and _private_ ✅")).toBe("Fix **kwargs** and _private_");
    expect(notificationTitle(notificationTitle("Fix **kwargs** and _private_"))).toBe("Fix **kwargs** and _private_");
  });
});

describe("legacyTitle", () => {
  it("cleans the markdown an older daemon sends in a frame title, code spans kept as written", () => {
    expect(legacyTitle("## **PR #482** is `ready` ✅")).toBe("PR #482 is ready");
    expect(legacyTitle("Fix `__init__` and `**kwargs**`")).toBe("Fix __init__ and **kwargs**");
    expect(legacyTitle("a\u00000\u0000b `c`")).toBe("a0b c");
  });
});

describe("notificationParts", () => {
  it("leads with the title and previews the summary", () => {
    expect(notificationParts({ title: "Sync failed", summary: "Exit 1 after 3 retries.", body: "detail" }))
      .toMatchObject({ title: "Sync failed", headline: "Sync failed", preview: "Exit 1 after 3 retries.", summary: "Exit 1 after 3 retries.", fromBody: false });
  });

  it("derives the summary from the body for an older daemon and marks it as the body's own", () => {
    const parts = notificationParts({ title: "Daily: normal", body: "**Normal day, lowest volume in eight days and nothing broke.**\n\n## Volume\n- 1,743 chats" });
    expect(parts.summary).toBe("Normal day, lowest volume in eight days and nothing broke.");
    expect(parts.fromBody).toBe(true);
  });

  it("treats a stored summary equal to the derived one as the body's own", () => {
    expect(notificationParts({ title: "T", summary: "Intro line: the point", body: "Intro line:\n- the point" }).fromBody).toBe(true);
  });

  it("splits the first sentence into the headline when there is no title", () => {
    expect(notificationParts({ body: "Recovery is low. HRV down 8ms vs baseline." }))
      .toMatchObject({ headline: "Recovery is low.", preview: "HRV down 8ms vs baseline." });
    expect(notificationParts({ body: "just a short note" })).toMatchObject({ headline: "just a short note", preview: "" });
    expect(notificationParts({ body: "```\ntrace\n```" }).headline).toBe("—");
  });

  it("exposes a given summary only when it is not the body's own opening", () => {
    expect(notificationParts({ title: "T", summary: "Moved to 11.", body: "## Detail\n- a" }).givenSummary).toBe("Moved to 11.");
    expect(notificationParts({ title: "T", summary: "Moved to 11.", body: "Moved to 11.\n\nmore" }).givenSummary).toBe("");
    expect(notificationParts({ title: "T", body: "Moved to 11." }).givenSummary).toBe("");
  });

  it("ignores a summary or body that is not text", () => {
    expect(notificationParts({ title: "T", summary: ["x"], body: 5 })).toMatchObject({ summary: "", body: "", headline: "T" });
  });

  it("keeps a plain title with stars and underscores intact", () => {
    expect(notificationParts({ title: "Fix **kwargs** and _private_", body: "x" }).headline).toBe("Fix **kwargs** and _private_");
  });

  it("keeps the status emoji in the preview", () => {
    expect(notificationParts({ title: "Recovery", body: "🔴 25% recovery." }).preview).toBe("🔴 25% recovery.");
  });
});

describe("notificationTime", () => {
  it("shows the clock inside the Today and Yesterday groups", () => {
    expect(notificationTime(at(0, 8, 1), { nowMs: NOW })).toBe(CLOCK.format(at(0, 8, 1) * 1000));
    expect(notificationTime(at(1, 16, 47), { nowMs: NOW })).toBe(CLOCK.format(at(1, 16, 47) * 1000));
  });

  it("adds the weekday inside This week and the date beyond it", () => {
    const d = new Date(at(3, 9) * 1000);
    expect(notificationTime(at(3, 9), { nowMs: NOW })).toBe(`${WEEKDAY.format(d)} ${CLOCK.format(d)}`);
    expect(notificationTime(at(20, 9), { nowMs: NOW })).not.toContain(":");
  });

  it("names the day outside a day group", () => {
    expect(notificationTime(at(1, 16), { nowMs: NOW, dayGroup: false })).toBe("Yesterday");
    expect(notificationTime(at(3, 9), { nowMs: NOW, dayGroup: false })).toBe(WEEKDAY.format(new Date(at(3, 9) * 1000)));
    expect(notificationTime(at(0, 8), { nowMs: NOW, dayGroup: false })).toBe(CLOCK.format(at(0, 8) * 1000));
  });

  it("is empty without a timestamp", () => {
    expect(notificationTime(0)).toBe("");
    expect(notificationStamp(0)).toBe("");
  });
});

describe("notificationStamp", () => {
  it("reads Today or Yesterday with the clock, never an age", () => {
    expect(notificationStamp(at(0, 8, 1), NOW)).toBe(`Today ${CLOCK.format(at(0, 8, 1) * 1000)}`);
    expect(notificationStamp(at(1, 16, 47), NOW)).toBe(`Yesterday ${CLOCK.format(at(1, 16, 47) * 1000)}`);
    expect(notificationStamp(at(0, 11, 59.9), NOW)).not.toMatch(/ago|now/);
  });

  it("gives the full date and clock further back", () => {
    const stamp = notificationStamp(at(20, 9), NOW);
    expect(stamp).toContain(CLOCK.format(at(20, 9) * 1000));
    expect(stamp).not.toMatch(/Today|Yesterday/);
  });
});
