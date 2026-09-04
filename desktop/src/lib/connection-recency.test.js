import { beforeEach, describe, expect, it } from "vitest";
import { orderConnections, readLastActive, stampLastActive } from "./connection-recency.js";

describe("connection recency", () => {
  beforeEach(() => localStorage.clear());

  it("keeps the local daemon first, recent reachable remotes next and unreachable ones last", () => {
    const rows = [
      { id: "mirai", kind: "remote", name: "mirai", status: "online" },
      { id: "down", kind: "remote", name: "alpi.mirai.com", status: "offline" },
      { id: "casa", kind: "remote", name: "casa", status: "online" },
      { id: "local", kind: "local", name: "Local daemon", status: "online" },
      { id: "satoshi", kind: "remote", name: "satoshi", status: "probing" },
    ];
    const ordered = orderConnections(rows, { casa: 300, satoshi: 200, down: 900 });
    expect(ordered.map((c) => c.id)).toEqual(["local", "casa", "satoshi", "mirai", "down"]);
  });

  it("stamps the connection picked last and reads it back", () => {
    stampLastActive("casa", 100);
    stampLastActive("mirai", 200);
    expect(readLastActive()).toEqual({ casa: 100, mirai: 200 });
    const ordered = orderConnections([
      { id: "casa", kind: "remote", name: "casa", status: "online" },
      { id: "mirai", kind: "remote", name: "mirai", status: "online" },
    ]);
    expect(ordered.map((c) => c.id)).toEqual(["mirai", "casa"]);
  });

  it("falls back to reachability and name when nothing was stamped", () => {
    localStorage.setItem("alpi.connections.lastActive.v1", "not json");
    const ordered = orderConnections([
      { id: "b", kind: "remote", name: "beta", status: "offline" },
      { id: "z", kind: "remote", name: "zeta", status: "online" },
      { id: "a", kind: "remote", name: "alpha", status: "online" },
    ]);
    expect(ordered.map((c) => c.id)).toEqual(["a", "z", "b"]);
  });
});
