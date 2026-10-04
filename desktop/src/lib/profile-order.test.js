import { describe, it, expect } from "vitest";

import { compareProfiles, orderedJumpTargets, orderedSidebarProfiles, orderPinnedItems } from "./profile-order.js";

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

describe("default profile first", () => {
  const profiles = [
    { name: "doc", model: "a/b", latest_session: { updated_at: 900 } },
    { name: "default", is_default: true, model: "a/b", paused: true, latest_session: { updated_at: 1 } },
    { name: "abby", model: "a/b", latest_session: { updated_at: 500 } },
    { name: "clonara", model: "a/b", latest_session: { updated_at: 100 } },
  ];

  it("leads the sidebar order above pins even when paused and quiet", () => {
    expect(orderedSidebarProfiles(profiles, ["clonara"]).map((p) => p.name)).toEqual([
      "default",
      "clonara",
      "doc",
      "abby",
    ]);
  });

  it("ignores a stale default pin", () => {
    expect(orderedSidebarProfiles(profiles, ["default"]).map((p) => p.name)).toEqual([
      "default",
      "doc",
      "abby",
      "clonara",
    ]);
  });

  it("maps ⌘1 to the default profile and shifts pins and the rest down", () => {
    const targets = orderedJumpTargets({
      profiles,
      workgroups: [{ profile: "doc", id: "roma" }],
      pinnedProfiles: ["clonara", "default"],
      pinnedWorkgroups: ["doc/roma"],
    });
    expect(targets.map((t) => t.target.name ?? t.target.id)).toEqual([
      "default",
      "clonara",
      "roma",
      "doc",
      "abby",
    ]);
  });

  it("keeps today's jump order on a connection without the default profile", () => {
    const scoped = profiles.filter((p) => p.name !== "default");
    const targets = orderedJumpTargets({ profiles: scoped, workgroups: [], pinnedProfiles: ["clonara"] });
    expect(targets.map((t) => t.target.name)).toEqual(["clonara", "doc", "abby"]);
  });
});

describe("jump targets follow the sidebar", () => {
  it("number the pinned rows in the order the Pinned section draws them", () => {
    const profiles = [
      { name: "default", is_default: true, model: "m" },
      { name: "a", model: "m", latest_session: { updated_at: 10 } },
      { name: "b", model: "m", latest_session: { updated_at: 20 } },
      { name: "c", model: "m", latest_session: { updated_at: 5 } },
    ];
    const workgroups = [{ profile: "a", id: "w", mtime: 30 }];
    const pinnedProfileNames = ["a", "b"];
    const pinned = pinnedProfileNames.map((n) => profiles.find((p) => p.name === n));
    const drawn = orderPinnedItems(pinned, workgroups).map((x) => x.item.name ?? x.item.id);
    const targets = orderedJumpTargets({ profiles, workgroups, pinnedProfiles: pinnedProfileNames, pinnedWorkgroups: ["a/w"] });
    expect(targets.map((t) => t.target.name ?? t.target.id)).toEqual(["default", ...drawn, "c"]);
    expect(drawn).toEqual(["w", "b", "a"]);
  });
});
