import { describe, it, expect, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";

import { EndpointContext } from "../lib/EndpointContext";
import { useProfile } from "./useSubject";

vi.mock("./useEvents", () => ({
  useEventEffect: vi.fn(),
}));

describe("useProfile endpoint switch", () => {
  it("clears `detail` synchronously when the endpoint's call ref flips, so settings/peers/MCP from the previous daemon don't bleed into the new screen", async () => {
    const detailByEndpoint = {
      alpha: { peers: [{ id: "peer-alpha" }] },
      beta: { peers: [{ id: "peer-beta" }] },
    };
    let activeKey = "alpha";
    const makeCall = (key) => async (method, params) => {
      if (method === "host.profile.summaries") {
        return { profiles: [{ name: params?.profile ?? "doc" }, { name: "doc" }] };
      }
      if (method === "host.profile.detail") {
        return detailByEndpoint[key];
      }
      return null;
    };

    let endpoint = { id: "alpha" };
    let call = makeCall("alpha");
    function Wrapper({ children }) {
      return (
        <EndpointContext.Provider value={{ endpoint, call }}>{children}</EndpointContext.Provider>
      );
    }

    const { result, rerender } = renderHook(() => useProfile("doc"), { wrapper: Wrapper });

    await waitFor(() =>
      expect(result.current.profile?.peers?.[0]?.id).toBe("peer-alpha"),
    );

    // Switch endpoint — new call ref points at beta.
    endpoint = { id: "beta" };
    activeKey = "beta";
    call = makeCall("beta");
    act(() => rerender());

    // Before beta resolves, detail must not still expose alpha's peers.
    expect(result.current.profile?.peers?.[0]?.id).not.toBe("peer-alpha");

    await waitFor(() =>
      expect(result.current.profile?.peers?.[0]?.id).toBe("peer-beta"),
    );
  });
});

describe("useProfile refreshDetail", () => {
  it("explicit refreshDetail() re-fetches host.profile.detail and updates `profile`", async () => {
    const responses = [
      { peers: [{ id: "alice" }] },
      { peers: [{ id: "alice" }, { id: "bob" }] },
    ];
    let i = 0;
    const call = async (method) => {
      if (method === "host.profile.summaries") {
        return { profiles: [{ name: "doc" }] };
      }
      if (method === "host.profile.detail") {
        return responses[Math.min(i++, responses.length - 1)];
      }
      return null;
    };
    function Wrapper({ children }) {
      return (
        <EndpointContext.Provider value={{ endpoint: { id: "x" }, call }}>{children}</EndpointContext.Provider>
      );
    }

    const { result } = renderHook(() => useProfile("doc"), { wrapper: Wrapper });
    await waitFor(() =>
      expect(result.current.profile?.peers).toEqual([{ id: "alice" }]),
    );

    await act(async () => {
      await result.current.refreshDetail();
    });

    await waitFor(() =>
      expect(result.current.profile?.peers).toEqual([
        { id: "alice" },
        { id: "bob" },
      ]),
    );
  });
});
