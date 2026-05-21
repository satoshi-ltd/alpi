import { describe, it, expect, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";

import { EndpointContext } from "../lib/EndpointContext";
import { useProfileSummaries } from "./useDaemonData";

describe("usePolledCall (via useProfileSummaries) endpoint switch", () => {
  it("clears snap synchronously when endpoint.id flips so the old endpoint's data does not bleed into the next render", async () => {
    const callsByEndpoint = {
      alpha: vi.fn(async () => ({ profiles: [{ name: "doc-alpha" }] })),
      beta: vi.fn(async () => ({ profiles: [{ name: "doc-beta" }] })),
    };
    function makeCall(ep) {
      return (method, params) => callsByEndpoint[ep.id](method, params);
    }

    const epAlpha = { id: "alpha", name: "alpha" };
    const epBeta = { id: "beta", name: "beta" };

    let currentEndpoint = epAlpha;
    let currentCall = makeCall(epAlpha);

    function Wrapper({ children }) {
      return (
        <EndpointContext.Provider value={{ endpoint: currentEndpoint, call: currentCall }}>
          {children}
        </EndpointContext.Provider>
      );
    }

    const { result, rerender } = renderHook(() => useProfileSummaries(), { wrapper: Wrapper });

    // Wait for alpha to populate.
    await waitFor(() =>
      expect(result.current.data?.profiles?.[0]?.name).toBe("doc-alpha"),
    );

    // Flip endpoint to beta (call also changes ref to point at beta).
    currentEndpoint = epBeta;
    currentCall = makeCall(epBeta);
    act(() => {
      rerender();
    });

    // CRITICAL: right after the endpoint flip — before beta's fetch resolves — snap must NOT still expose alpha's data.
    expect(result.current.data?.profiles?.[0]?.name).not.toBe("doc-alpha");
    expect(result.current.loading).toBe(true);

    // beta's data lands.
    await waitFor(() =>
      expect(result.current.data?.profiles?.[0]?.name).toBe("doc-beta"),
    );
  });

  it("a late-resolving inflight on the PREVIOUS endpoint does not clobber the current snap after a key flip", async () => {
    let resolveStale;
    const staleCall = vi.fn(
      () =>
        new Promise((resolve) => {
          resolveStale = resolve;
        }),
    );
    const freshCall = vi.fn(async () => ({ profiles: [{ name: "doc-fresh" }] }));
    const makeCall = (key) => (method, params) =>
      (key === "stale-ep" ? staleCall : freshCall)(method, params);

    let currentEndpoint = { id: "stale-ep" };
    let currentCall = makeCall("stale-ep");
    function Wrapper({ children }) {
      return (
        <EndpointContext.Provider value={{ endpoint: currentEndpoint, call: currentCall }}>
          {children}
        </EndpointContext.Provider>
      );
    }

    const { result, rerender } = renderHook(() => useProfileSummaries(), { wrapper: Wrapper });
    await waitFor(() => expect(staleCall).toHaveBeenCalledTimes(1));

    currentEndpoint = { id: "fresh-ep" };
    currentCall = makeCall("fresh-ep");
    act(() => rerender());
    await waitFor(() => expect(result.current.data?.profiles?.[0]?.name).toBe("doc-fresh"));

    // NOW resolve the stale promise — the captured-key listener guard must skip the setSnap call.
    await act(async () => {
      resolveStale({ profiles: [{ name: "STALE-doc" }] });
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(result.current.data?.profiles?.[0]?.name).toBe("doc-fresh");
  });
});
