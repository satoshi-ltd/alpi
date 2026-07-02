import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";

import { EndpointContext } from "../lib/EndpointContext";
import { _resetDaemonDataCache, useProfileSnapshot, useProfileSummaries, useSession } from "./useDaemonData";

beforeEach(() => {
  _resetDaemonDataCache();
});

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

describe("useProfileSnapshot", () => {
  it("returns cached settings immediately while refreshing in the background", async () => {
    const call = vi.fn()
      .mockResolvedValueOnce({ detail: { name: "doc" }, usage: { days: [] } })
      .mockResolvedValueOnce({ detail: { name: "doc", model: "openrouter/x" }, usage: { days: [] } });

    function Wrapper({ children }) {
      return (
        <EndpointContext.Provider value={{ endpoint: { id: "alpha" }, call }}>
          {children}
        </EndpointContext.Provider>
      );
    }

    const first = renderHook(() => useProfileSnapshot("doc"), { wrapper: Wrapper });
    await waitFor(() => expect(first.result.current.data?.detail?.name).toBe("doc"));
    first.unmount();

    const second = renderHook(() => useProfileSnapshot("doc"), { wrapper: Wrapper });
    expect(second.result.current.data?.detail?.name).toBe("doc");
    expect(second.result.current.loading).toBe(true);

    await act(async () => {
      await second.result.current.refresh();
    });

    expect(second.result.current.data?.detail?.model).toBe("openrouter/x");
  });

  it("keeps cached settings on transient failure", async () => {
    const call = vi.fn()
      .mockResolvedValueOnce({ detail: { name: "doc" }, schedules: { jobs: [{ id: "daily" }] } })
      .mockRejectedValueOnce(new Error("network down"));

    function Wrapper({ children }) {
      return (
        <EndpointContext.Provider value={{ endpoint: { id: "remote" }, call }}>
          {children}
        </EndpointContext.Provider>
      );
    }

    const { result } = renderHook(() => useProfileSnapshot("doc"), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.data?.schedules?.jobs?.[0]?.id).toBe("daily"));

    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.data?.schedules?.jobs?.[0]?.id).toBe("daily");
    expect(result.current.error?.message).toBe("network down");
  });

  it("keeps cached settings on request timeout even though mobile timeouts use code -32000", async () => {
    const timeout = new Error("request timed out after 10000ms");
    timeout.code = -32000;
    const call = vi.fn()
      .mockResolvedValueOnce({ detail: { name: "doc" } })
      .mockRejectedValueOnce(timeout);

    function Wrapper({ children }) {
      return (
        <EndpointContext.Provider value={{ endpoint: { id: "slow" }, call }}>
          {children}
        </EndpointContext.Provider>
      );
    }

    const { result } = renderHook(() => useProfileSnapshot("doc"), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.data?.detail?.name).toBe("doc"));

    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.data?.detail?.name).toBe("doc");
    expect(result.current.error?.message).toContain("timed out");
  });


  it("drops cached settings on auth failure", async () => {
    const auth = new Error("auth-failed");
    auth.code = -32000;
    const call = vi.fn()
      .mockResolvedValueOnce({ detail: { name: "doc" } })
      .mockRejectedValueOnce(auth);

    function Wrapper({ children }) {
      return (
        <EndpointContext.Provider value={{ endpoint: { id: "secure" }, call }}>
          {children}
        </EndpointContext.Provider>
      );
    }

    const { result } = renderHook(() => useProfileSnapshot("doc"), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.data?.detail?.name).toBe("doc"));

    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.data).toBe(null);
    expect(result.current.error?.message).toBe("auth-failed");
  });

  it("marks method-not-found as unsupported for section fallback", async () => {
    const err = new Error("method-not-found");
    err.code = -32601;
    const call = vi.fn().mockRejectedValue(err);

    function Wrapper({ children }) {
      return (
        <EndpointContext.Provider value={{ endpoint: { id: "old" }, call }}>
          {children}
        </EndpointContext.Provider>
      );
    }

    const { result } = renderHook(() => useProfileSnapshot("doc"), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.unsupported).toBe(true));
  });
});

describe("useSession tail slicing", () => {
  function wrapperWith(call) {
    const endpoint = { id: "ep1", name: "ep1" };
    return function Wrapper({ children }) {
      return (
        <EndpointContext.Provider value={{ endpoint, call }}>
          {children}
        </EndpointContext.Provider>
      );
    };
  }

  it("passes tail_turns through and exposes total/offset from the envelope", async () => {
    const call = vi.fn(async () => ({
      session: { id: "s1", turns: [{ user: "u2" }] },
      total_turns: 3,
      turns_offset: 2,
    }));
    const { result } = renderHook(() => useSession("doc", "s1", 1), {
      wrapper: wrapperWith(call),
    });
    await waitFor(() => expect(result.current.data?.id).toBe("s1"));
    expect(call).toHaveBeenCalledWith("host.session.read", {
      profile: "doc", id: "s1", tail_turns: 1,
    });
    expect(result.current.totalTurns).toBe(3);
    expect(result.current.turnsOffset).toBe(2);
  });

  it("treats a daemon that ignored the slice as a full transcript (totalTurns null, offset 0)", async () => {
    const call = vi.fn(async () => ({
      session: { id: "s1", turns: [{ user: "u0" }, { user: "u1" }] },
    }));
    const { result } = renderHook(() => useSession("doc", "s1", 1), {
      wrapper: wrapperWith(call),
    });
    await waitFor(() => expect(result.current.data?.turns).toHaveLength(2));
    expect(result.current.totalTurns).toBeNull();
    expect(result.current.turnsOffset).toBe(0);
  });

  it("omits tail_turns when not requested", async () => {
    const call = vi.fn(async () => ({ session: { id: "s1", turns: [] } }));
    renderHook(() => useSession("doc", "s1"), { wrapper: wrapperWith(call) });
    await waitFor(() => expect(call).toHaveBeenCalledWith("host.session.read", {
      profile: "doc", id: "s1",
    }));
  });
});

describe("useProfileSnapshot sections", () => {
  it("requests every section except storage so the snapshot never pays the os.walk", async () => {
    const call = vi.fn(async () => ({ detail: {} }));
    const endpoint = { id: "ep1", name: "ep1" };
    function Wrapper({ children }) {
      return (
        <EndpointContext.Provider value={{ endpoint, call }}>
          {children}
        </EndpointContext.Provider>
      );
    }
    renderHook(() => useProfileSnapshot("doc"), { wrapper: Wrapper });
    await waitFor(() => expect(call).toHaveBeenCalledWith("host.settings.profile_snapshot", {
      profile: "doc",
      sections: ["detail", "usage", "workgroups", "email", "schedules"],
    }));
  });
});
