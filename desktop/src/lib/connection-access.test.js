import { describe, expect, it } from "vitest";

import { connectionCanManage } from "./connection-access.js";

const CONNECTIONS = [
  { id: "local", kind: "local", role: null },
  { id: "admin-b", kind: "remote", role: "admin" },
  { id: "member-a", kind: "remote", role: "member" },
  { id: "unprobed", kind: "remote", role: null },
];

describe("connectionCanManage", () => {
  it("lets the local daemon and an admin connection manage", () => {
    expect(connectionCanManage(CONNECTIONS, "local")).toBe(true);
    expect(connectionCanManage(CONNECTIONS, "admin-b")).toBe(true);
  });

  it("refuses a member connection", () => {
    expect(connectionCanManage(CONNECTIONS, "member-a")).toBe(false);
  });

  it("treats a role that has not been probed yet like the rest of the app does, as allowed", () => {
    expect(connectionCanManage(CONNECTIONS, "unprobed")).toBe(true);
  });

  it("refuses a connection it does not know, and survives no list at all", () => {
    expect(connectionCanManage(CONNECTIONS, "gone")).toBe(false);
    expect(connectionCanManage(undefined, "local")).toBe(false);
  });
});
