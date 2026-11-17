import { describe, expect, it } from "vitest";
import { introAge, introBio, introSession } from "../../../common/threadIntro.mjs";

describe("threadIntro", () => {
  it("reads the bio on one line, falling back to public_bio, and nothing when blank", () => {
    expect(introBio({ bio: "  Keeps the\n knowledge base   current " })).toBe("Keeps the knowledge base current");
    expect(introBio({ public_bio: "Copywriter" })).toBe("Copywriter");
    expect(introBio({ bio: "   " })).toBeNull();
    expect(introBio(null)).toBeNull();
  });

  it("offers the latest chat session by its first message and its newest time", () => {
    expect(introSession({ latest_session: { id: "s", kind: "chat", first_user: " Hi\n there ", updated_at: 30, mtime: 20, started_at: 10 } }))
      .toEqual({ id: "s", title: "Hi there", ts: 30 });
    expect(introSession({ latest_session: { id: "s", first_user: "Hi", mtime: 20 } })).toEqual({ id: "s", title: "Hi", ts: 20 });
  });

  it("offers nothing for a workgroup session, an untitled one or none", () => {
    expect(introSession({ latest_session: { id: "w", kind: "workgroup", first_user: "post" } })).toBeNull();
    expect(introSession({ latest_session: { id: "s", kind: "chat", first_user: "" } })).toBeNull();
    expect(introSession({ latest_session: { kind: "chat", first_user: "Hi" } })).toBeNull();
    expect(introSession({})).toBeNull();
  });

  it("writes the age the way the desktop lists do, up to weeks", () => {
    const now = Date.UTC(2026, 10, 17, 12);
    const ago = (s) => Math.floor(now / 1000) - s;
    expect(introAge(0, now)).toBe("");
    expect(introAge(ago(20), now)).toBe("now");
    expect(introAge(ago(5 * 60), now)).toBe("5m");
    expect(introAge(ago(3 * 3600), now)).toBe("3h");
    expect(introAge(ago(2 * 86400), now)).toBe("2d");
    expect(introAge(ago(8 * 86400), now)).toBe("1w");
    expect(introAge(ago(40 * 86400), now)).not.toMatch(/^\d+[mhdw]$/);
  });
});
