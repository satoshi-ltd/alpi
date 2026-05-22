import { describe, it, expect } from "vitest";

import { resolveCancelAction } from "./device-pair";

describe("resolveCancelAction", () => {
  it("noop when no token has been generated yet (modal closed before generate completed)", () => {
    expect(resolveCancelAction([], "", "anything")).toEqual({ kind: "noop" });
    expect(resolveCancelAction([], undefined, "anything")).toEqual({ kind: "noop" });
  });

  it("revokes when the phone never used the token (last_seen still null)", () => {
    const devices = [
      { token_id: "abc12345", label: "", created: 1, last_seen: null },
    ];
    expect(resolveCancelAction(devices, "abc12345", "iPhone")).toEqual({ kind: "revoke" });
  });

  it("revokes when the token is missing from the list (defensive: treat as never-used)", () => {
    expect(resolveCancelAction([], "abc12345", "iPhone")).toEqual({ kind: "revoke" });
  });

  it("keeps the device when the phone already used the token", () => {
    const devices = [
      { token_id: "abc12345", label: "", created: 1, last_seen: 1779428754 },
    ];
    expect(resolveCancelAction(devices, "abc12345", "iPhone")).toEqual({
      kind: "keep",
      label: "iPhone",
    });
  });

  it("falls back to Unnamed device when keep happens with an empty label", () => {
    const devices = [
      { token_id: "abc12345", label: "", created: 1, last_seen: 1779428754 },
    ];
    expect(resolveCancelAction(devices, "abc12345", "")).toEqual({
      kind: "keep",
      label: "Unnamed device",
    });
    expect(resolveCancelAction(devices, "abc12345", "   ")).toEqual({
      kind: "keep",
      label: "Unnamed device",
    });
  });

  it("treats a non-array list as empty so an upstream rpc error degrades to revoke instead of crashing", () => {
    expect(resolveCancelAction(null, "abc12345", "iPhone")).toEqual({ kind: "revoke" });
    expect(resolveCancelAction({ devices: [] }, "abc12345", "iPhone")).toEqual({ kind: "revoke" });
  });
});
