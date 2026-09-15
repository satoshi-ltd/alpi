import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";

import { connectionEndpoint, pairingFailureNotice, useFireOnce } from "./ConnectionSwitcher.jsx";
import { RATE_LIMITED_MESSAGE } from "../lib/connection-status.js";

describe("pairingFailureNotice", () => {
  it("explains a throttled pairing exchange without blaming the code", () => {
    const notice = pairingFailureNotice("websocket closed by daemon (1013 auth-rate-limited)");
    expect(notice.message).toBe(RATE_LIMITED_MESSAGE);
    expect(notice.variant).toBe("warning");
    expect(notice.message).not.toMatch(/re-pair|token/i);
  });

  it("keeps the generic wording for every other failure", () => {
    expect(pairingFailureNotice("alp -32011: pairing-invalid").message).toBe(
      "Pairing failed: alp -32011: pairing-invalid",
    );
  });
});

describe("connectionEndpoint", () => {
  it("shows the complete URL returned for current remote connections", () => {
    expect(connectionEndpoint({ kind: "remote", url: "wss://client.example.com" })).toBe(
      "wss://client.example.com",
    );
  });

  it("keeps legacy host and port connections readable", () => {
    expect(connectionEndpoint({ kind: "remote", host: "casa", port: 49200 })).toBe(
      "casa:49200",
    );
  });

  it("never renders undefined fields for incomplete saved connections", () => {
    expect(connectionEndpoint({ kind: "remote", host: "casa" })).toBe("casa");
    expect(connectionEndpoint({ kind: "remote" })).toBe("endpoint unavailable");
    expect(connectionEndpoint({ kind: "local" })).toBe("host.sock");
  });
});

describe("useFireOnce", () => {
  it("fires the callback the first time signal becomes truthy", () => {
    const cb = vi.fn();
    const { rerender } = renderHook(({ signal }) => useFireOnce(signal, cb), {
      initialProps: { signal: false },
    });
    expect(cb).not.toHaveBeenCalled();
    rerender({ signal: true });
    expect(cb).toHaveBeenCalledTimes(1);
  });

  it("does not re-fire on a second false→true transition (once-per-session)", () => {
    const cb = vi.fn();
    const { rerender } = renderHook(({ signal }) => useFireOnce(signal, cb), {
      initialProps: { signal: true },
    });
    expect(cb).toHaveBeenCalledTimes(1);
    rerender({ signal: false });
    rerender({ signal: true });
    expect(cb).toHaveBeenCalledTimes(1);
  });

  it("does not fire when signal is never truthy", () => {
    const cb = vi.fn();
    const { rerender } = renderHook(({ signal }) => useFireOnce(signal, cb), {
      initialProps: { signal: false },
    });
    rerender({ signal: false });
    expect(cb).not.toHaveBeenCalled();
  });
});
