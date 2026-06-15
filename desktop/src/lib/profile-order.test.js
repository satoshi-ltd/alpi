import { describe, it, expect } from "vitest";

import { compareProfiles, orderedSidebarProfiles, orderPinnedItems } from "./profile-order.js";

describe("orderedSidebarProfiles", () => {
  it("sorts paused profiles last — after even the incomplete ones", () => {
    const profiles = [
      { name: "active", model: "a/b", latest_session: { updated_at: 100 } },
      { name: "paused", model: "a/b", paused: true, latest_session: { updated_at: 999 } },
      { name: "incomplete" },
    ];
    const order = orderedSidebarProfiles(profiles).map((p) => p.name);
    expect(order).toEqual(["active", "incomplete", "paused"]);
  });

  it("keeps a pinned profile on top even when paused", () => {
    const profiles = [
      { name: "a", model: "x/y", latest_session: { updated_at: 10 } },
      { name: "p", model: "x/y", paused: true },
    ];
    expect(orderedSidebarProfiles(profiles, ["p"]).map((x) => x.name)[0]).toBe("p");
  });
});

describe("compareProfiles", () => {
  it("orders paused last, then incomplete, then most-recent first", () => {
    const profiles = [
      { name: "paused", model: "a/b", paused: true, latest_session: { updated_at: 999 } },
      { name: "old", model: "a/b", latest_session: { updated_at: 10 } },
      { name: "incomplete" },
      { name: "recent", model: "a/b", latest_session: { updated_at: 500 } },
    ];
    expect([...profiles].sort(compareProfiles).map((p) => p.name)).toEqual([
      "recent",
      "old",
      "incomplete",
      "paused",
    ]);
  });

  it("sinks a paused profile below active ones in the same group", () => {
    const pinned = [
      { name: "active", model: "a/b", latest_session: { updated_at: 1 } },
      { name: "dozing", model: "a/b", paused: true, latest_session: { updated_at: 999 } },
    ];
    expect([...pinned].sort(compareProfiles).map((p) => p.name)).toEqual(["active", "dozing"]);
  });
});

describe("orderPinnedItems", () => {
  it("sinks a paused pinned profile below active pins, even if more recent", () => {
    const profiles = [
      { name: "paused", model: "a/b", paused: true, latest_session: { updated_at: 999 } },
      { name: "active", model: "a/b", latest_session: { updated_at: 10 } },
    ];
    expect(orderPinnedItems(profiles, []).map((x) => x.item.name)).toEqual(["active", "paused"]);
  });

  it("sinks an incomplete (no model) pinned profile too", () => {
    const profiles = [
      { name: "incomplete" },
      { name: "active", model: "a/b", latest_session: { updated_at: 5 } },
    ];
    expect(orderPinnedItems(profiles, []).map((x) => x.item.name)).toEqual(["active", "incomplete"]);
  });

  it("mixes pinned profiles and workgroups, paused of either kind last", () => {
    const profiles = [{ name: "p", model: "a/b", latest_session: { updated_at: 100 } }];
    const workgroups = [
      { id: "live", profile: "p", mtime: 50 },
      { id: "frozen", profile: "p", paused: true, mtime: 999 },
    ];
    expect(orderPinnedItems(profiles, workgroups).map((x) => x.kind + ":" + (x.item.name ?? x.item.id))).toEqual([
      "profile:p",
      "workgroup:live",
      "workgroup:frozen",
    ]);
  });
});
