import { describe, expect, it } from "vitest";
import {
  failedStep,
  memberEmptyCopy,
  pairedRoleLine,
  pairingFailure,
  pairingFailureKind,
  pairingLinkHost,
  pairingStepLabel,
} from "../../../common/onboarding.mjs";
import { emptyCopyProblems } from "../../../common/emptyCopy.rules.mjs";

describe("onboarding copy", () => {
  it("maps every probe status and transport error to one named failure", () => {
    expect(pairingFailureKind("offline")).toBe("unreachable");
    expect(pairingFailureKind(new Error("request timed out after 10000ms"))).toBe("unreachable");
    expect(pairingFailureKind("auth-failed")).toBe("link-used");
    expect(pairingFailureKind("alp -32011: pairing-used — pairing code already used")).toBe("link-used");
    expect(pairingFailureKind("disabled")).toBe("disabled");
    expect(pairingFailureKind(new Error("-32601 method-not-found"))).toBe("too-old");
    expect(pairingFailureKind(new Error("Too many authentication attempts from this IP"))).toBe("rate-limited");
    expect(pairingFailureKind("websocket closed by daemon (1013 auth-rate-limited)")).toBe("rate-limited");
    expect(pairingFailureKind("alp -32011: pairing-invalid")).toBe("link-used");
    expect(pairingFailureKind(new Error("boom"))).toBe("unknown");
  });

  it("reads the daemon's and the transports' real errors, code first", () => {
    expect(pairingFailureKind(Object.assign(new Error("pairing-used"), { code: -32011 }))).toBe("link-used");
    expect(pairingFailureKind(Object.assign(new Error("pairing-expired"), { code: -32011 }))).toBe("link-used");
    expect(pairingFailureKind(Object.assign(new Error("connection failed to ws://100.1.2.3:49200"), { code: -32001, transport: true }))).toBe("unreachable");
    expect(pairingFailureKind(Object.assign(new Error("forbidden"), { code: -32001 }))).toBe("unknown");
    expect(pairingFailureKind('cannot resolve host "casa.local": failed to lookup address')).toBe("unreachable");
    expect(pairingFailureKind("websocket handshake read: Connection reset by peer")).toBe("unreachable");
    expect(pairingFailureKind("alp -32000: auth-failed — connection-disabled")).toBe("disabled");
    expect(pairingFailureKind("invalid peer certificate: Expired")).not.toBe("link-used");
    expect(pairingFailureKind("pairing payload needs a URL or a host and port")).toBe("invalid");
    expect(pairingFailureKind("websocket closed by daemon (1006)")).toBe("unreachable");
    expect(pairingFailureKind("cannot resolve ~/.alpi")).toBe("unknown");
  });

  it("names the host and says whether the link survives", () => {
    expect(pairingFailure("unreachable", "casa")).toMatchObject({ title: "Can't reach casa", keepLink: true, action: "Try again" });
    expect(pairingFailure("link-used", "casa")).toMatchObject({ keepLink: false, action: "Use a new link" });
    expect(pairingFailure("nonsense", "casa").kind).toBe("unknown");
    expect(failedStep("invalid")).toBe("read");
    expect(failedStep("unreachable")).toBe("reach");
    expect(failedStep("link-used")).toBe("sign-in");
    expect(pairingStepLabel("reach", "casa")).toBe("Reaching casa");
  });

  it("reads the host from a pairing link", () => {
    expect(pairingLinkHost("alpi://device?url=ws%3A%2F%2F100.1.2.3%3A49200&name=casa")).toBe("casa");
    expect(pairingLinkHost("alpi://device?url=wss%3A%2F%2Fhost.example.com")).toBe("host.example.com");
    expect(pairingLinkHost("alpi://device?host=100.1.2.3&port=49200&token=abc")).toBe("100.1.2.3");
    expect(pairingLinkHost("https://example.com")).toBeNull();
  });

  it("says the role after pairing and keeps the member copy within the empty-state rules", () => {
    expect(pairedRoleLine("admin")).toBe("admin · all profiles");
    expect(pairedRoleLine("member", 1)).toBe("member · 1 profile shared");
    expect(pairedRoleLine("member", 0)).toBe("member · nothing shared yet");
    expect(memberEmptyCopy("this phone").hint).toBe("Ask the host admin to share a profile with this phone.");
    expect(emptyCopyProblems({ member: memberEmptyCopy(null) })).toEqual([]);
  });
});
