import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";

import { EndpointContext } from "../lib/EndpointContext";
import { _resetDaemonDataCache, useProfileMemory, useProfileSnapshot, useProfileSummaries } from "./useDaemonData";

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

  it("keeps cached settings when the connection is disabled", async () => {
    const disabled = new Error("auth-failed");
    disabled.code = -32000;
    disabled.data = { reason: "connection-disabled" };
    const call = vi.fn()
      .mockResolvedValueOnce({ detail: { name: "doc" } })
      .mockRejectedValueOnce(disabled);

    function Wrapper({ children }) {
      return (
        <EndpointContext.Provider value={{ endpoint: { id: "paused" }, call }}>
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
    expect(result.current.error?.data?.reason).toBe("connection-disabled");
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

describe('seedCache + useSessionsList skipWhen', () => {
  it('seedCache pre-populates a key so a consumer paints synchronously without fetching', async () => {
    const { seedCache, useProfileSummaries } = await import('./useDaemonData');
    const payload = { profiles: [{ name: 'seeded' }] };
    seedCache('ep-seed', 'host.profile.summaries', {}, payload);
    const call = vi.fn(async () => ({ profiles: [{ name: 'fresh' }] }));
    const endpoint = { id: 'ep-seed', name: 'ep-seed' };
    function Wrapper({ children }) {
      return (
        <EndpointContext.Provider value={{ endpoint, call }}>{children}</EndpointContext.Provider>
      );
    }
    const { result } = renderHook(() => useProfileSummaries(), { wrapper: Wrapper });
    // Synchronous first paint from the seed, before any fetch resolves.
    expect(result.current.data).toEqual(payload);
    await waitFor(() => expect(result.current.data?.profiles?.[0]?.name).toBe('fresh'));
  });

  it('useSessionsList with skipWhen:true issues no RPC', async () => {
    const { useSessionsList } = await import('./useDaemonData');
    const call = vi.fn(async () => ({ sessions: [] }));
    const endpoint = { id: 'ep1', name: 'ep1' };
    function Wrapper({ children }) {
      return (
        <EndpointContext.Provider value={{ endpoint, call }}>{children}</EndpointContext.Provider>
      );
    }
    renderHook(() => useSessionsList('doc', 30, { skipWhen: true }), { wrapper: Wrapper });
    await Promise.resolve();
    expect(call).not.toHaveBeenCalled();
  });
});

describe("useWorkgroupTasks", () => {
  const RUN = {
    active: { slug: "media-build", title: "rebuild", opened_seq: 43 },
    closed: [{ slug: "media-config", result: "skipped · no config change", closed_seq: 42, blocked: false }],
    blocked: null,
    pipeline_run: {
      pipeline: "media-update",
      status: "running",
      started_seq: 37,
      current_phase: "media-build",
      phases: [
        { slug: "media-update", state: "completed", seq: 40 },
        { slug: "media-config", state: "skipped", seq: 42 },
        { slug: "media-build", state: "current", seq: 43 },
        { slug: "media-qa", state: "pending", seq: null },
      ],
    },
  };

  function wrapperFor(call, endpoint = { id: "ep1" }) {
    return ({ children }) => (
      <EndpointContext.Provider value={{ endpoint, call }}>{children}</EndpointContext.Provider>
    );
  }

  it("asks the daemon for the canonical fold", async () => {
    const { useWorkgroupTasks } = await import("./useDaemonData");
    const call = vi.fn(async () => RUN);
    const { result } = renderHook(() => useWorkgroupTasks("mira", "wg1"), { wrapper: wrapperFor(call) });
    await waitFor(() => expect(result.current.data?.pipeline_run?.pipeline).toBe("media-update"));
    expect(call).toHaveBeenCalledWith("host.workgroup.tasks", { profile: "mira", wg_id: "wg1" });
    expect(result.current.data.pipeline_run.phases[1].state).toBe("skipped");
  });

  it("issues no RPC without a profile or a workgroup", async () => {
    const { useWorkgroupTasks } = await import("./useDaemonData");
    const call = vi.fn(async () => RUN);
    renderHook(() => useWorkgroupTasks(null, "wg1"), { wrapper: wrapperFor(call) });
    renderHook(() => useWorkgroupTasks("mira", null), { wrapper: wrapperFor(call) });
    await Promise.resolve();
    expect(call).not.toHaveBeenCalled();
  });

  it("refresh re-folds so an ad-hoc task drops the prior run", async () => {
    const { useWorkgroupTasks } = await import("./useDaemonData");
    const call = vi.fn()
      .mockResolvedValueOnce(RUN)
      .mockResolvedValueOnce({
        active: { slug: "hotfix", title: "patch", opened_seq: 60 },
        closed: [],
        blocked: null,
        pipeline_run: null,
      });
    const { result } = renderHook(() => useWorkgroupTasks("mira", "wg1"), { wrapper: wrapperFor(call) });
    await waitFor(() => expect(result.current.data?.pipeline_run).toBeTruthy());

    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.data.pipeline_run).toBe(null);
    expect(result.current.data.active.slug).toBe("hotfix");
  });
});

describe("useProfileMemory", () => {
  it("exposes per-file usage alongside the raw text", async () => {
    const call = vi.fn(async (method) => {
      if (method === "host.profile.read_file") return { text: "body" };
      if (method === "host.profile.memory_usage") {
        return { files: { "AGENT.md": { used: 4000, limit: 8000, pct: 50, over: false } } };
      }
      return {};
    });
    const endpoint = { id: "e1", name: "e1" };
    function Wrapper({ children }) {
      return (
        <EndpointContext.Provider value={{ endpoint, call }}>{children}</EndpointContext.Provider>
      );
    }
    const { result } = renderHook(() => useProfileMemory("doc"), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.usage).toBeTruthy());
    expect(result.current.usage["AGENT.md"].pct).toBe(50);
  });

  it("clears the previous scope synchronously so it never paints after a profile flip", async () => {
    const call = vi.fn(async (method, params) => {
      if (method === "host.profile.read_file") {
        return { text: params.rel_path.includes("AGENT") ? `body-${params.profile}` : "" };
      }
      return { files: {} };
    });
    const endpoint = { id: "e1" };
    const Wrapper = ({ children }) => (
      <EndpointContext.Provider value={{ endpoint, call }}>{children}</EndpointContext.Provider>
    );
    const { result, rerender } = renderHook(({ p }) => useProfileMemory(p), {
      wrapper: Wrapper,
      initialProps: { p: "alpha" },
    });
    await waitFor(() => expect(result.current.data?.["AGENT.md"]).toBe("body-alpha"));

    act(() => rerender({ p: "beta" }));
    expect(result.current.data).toBe(null);
    expect(result.current.loading).toBe(true);

    await waitFor(() => expect(result.current.data?.["AGENT.md"]).toBe("body-beta"));
  });

  it("drops a pending read when the endpoint disappears before it resolves", async () => {
    let resolveRead;
    const call = vi.fn((method) => {
      if (method === "host.profile.read_file") {
        return new Promise((r) => { resolveRead = () => r({ text: "late" }); });
      }
      return Promise.resolve({ files: {} });
    });
    let endpoint = { id: "e1" };
    const Wrapper = ({ children }) => (
      <EndpointContext.Provider value={{ endpoint, call }}>{children}</EndpointContext.Provider>
    );
    const { result, rerender } = renderHook(() => useProfileMemory("doc"), { wrapper: Wrapper });
    await waitFor(() => expect(call).toHaveBeenCalled());

    endpoint = null;
    act(() => rerender());
    expect(result.current.data).toBe(null);
    expect(result.current.loading).toBe(false);

    await act(async () => { resolveRead(); await Promise.resolve(); await Promise.resolve(); });
    expect(result.current.data).toBe(null);
  });
});

describe("usePolledCall error latch", () => {
  it("keeps the error up while a retry is in flight, so a warning never blinks off mid-poll", async () => {
    _resetDaemonDataCache();
    let failSecond;
    const call = vi
      .fn()
      .mockRejectedValueOnce(new Error("timeout"))
      .mockImplementationOnce(() => new Promise((_, rej) => { failSecond = () => rej(new Error("timeout")); }));
    const endpoint = { id: "latch-1", name: "casa" };
    const wrapper = ({ children }) => (
      <EndpointContext.Provider value={{ endpoint, call }}>{children}</EndpointContext.Provider>
    );
    const { result } = renderHook(() => useProfileSummaries(), { wrapper });

    await waitFor(() => expect(result.current.error).toBeTruthy());
    await act(async () => { result.current.refresh(); });
    expect(result.current.error).toBeTruthy();
    await act(async () => { failSecond(); await Promise.resolve(); });
    expect(result.current.error).toBeTruthy();
  });

  it("clears the error only when a read finally succeeds", async () => {
    _resetDaemonDataCache();
    const call = vi
      .fn()
      .mockRejectedValueOnce(new Error("timeout"))
      .mockResolvedValue({ profiles: [] });
    const endpoint = { id: "latch-2", name: "casa" };
    const wrapper = ({ children }) => (
      <EndpointContext.Provider value={{ endpoint, call }}>{children}</EndpointContext.Provider>
    );
    const { result } = renderHook(() => useProfileSummaries(), { wrapper });

    await waitFor(() => expect(result.current.error).toBeTruthy());
    await act(async () => { await result.current.refresh().catch(() => {}); });
    await waitFor(() => expect(result.current.error).toBeNull());
  });
});
