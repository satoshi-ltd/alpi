import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const invokeMock = vi.fn();
const fetchWorkgroupTranscriptMock = vi.fn();

vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args) => invokeMock(...args),
}));

vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(async () => vi.fn()),
}));

vi.mock("../lib/workgroup-fetch.js", () => ({
  fetchWorkgroupTranscript: (...args) => fetchWorkgroupTranscriptMock(...args),
}));

vi.mock("../hooks/useProfileDetail.js", () => ({
  useProfileDetail: () => ({ detail: null }),
}));

import WorkgroupView from "./WorkgroupView.jsx";

globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

const workgroup = {
  id: "launch",
  profile: "hub",
  hub_id: "hub",
  paused: false,
  auto_read: false,
  members: 1,
};

const profiles = [
  {
    name: "hub",
    accent: "#5588ff",
    pubkey_b64: "hub-pubkey",
  },
];

beforeEach(() => {
  invokeMock.mockReset();
  invokeMock.mockResolvedValue("");
  fetchWorkgroupTranscriptMock.mockReset();
  fetchWorkgroupTranscriptMock.mockResolvedValue([]);
});

describe("WorkgroupView command ticks", () => {
  it("refreshes only when the external refresh tick changes", async () => {
    const { rerender } = render(
      <WorkgroupView
        workgroup={workgroup}
        profiles={profiles}
        connectionId="local"
        refreshCommandTick={1}
      />,
    );

    await waitFor(() => expect(fetchWorkgroupTranscriptMock).toHaveBeenCalledTimes(1));

    rerender(
      <WorkgroupView
        workgroup={workgroup}
        profiles={profiles}
        connectionId="local"
        refreshCommandTick={2}
      />,
    );

    await waitFor(() => expect(fetchWorkgroupTranscriptMock).toHaveBeenCalledTimes(2));
  });

  it("pauses only when the external pause tick changes", async () => {
    const { rerender } = render(
      <WorkgroupView
        workgroup={workgroup}
        profiles={profiles}
        connectionId="local"
        pauseCommandTick={1}
      />,
    );
    await act(async () => {});

    expect(invokeMock).not.toHaveBeenCalledWith(
      "workgroup_action",
      expect.anything(),
    );

    rerender(
      <WorkgroupView
        workgroup={workgroup}
        profiles={profiles}
        connectionId="local"
        pauseCommandTick={2}
      />,
    );

    await waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith("workgroup_action", {
        profile: "hub",
        wgId: "launch",
        action: "pause",
        connectionId: "local",
      }),
    );
  });

  it("uses structured workgroup data without rereading raw files", async () => {
    fetchWorkgroupTranscriptMock.mockResolvedValue([{
      seq: 1,
      from_pubkey: "hub-pubkey",
      body: "done",
      cost: { tokens: 42, usd: 0.0042 },
    }]);
    render(
      <WorkgroupView
        workgroup={workgroup}
        profiles={profiles}
        connectionId="local"
      />,
    );

    await waitFor(() => expect(fetchWorkgroupTranscriptMock).toHaveBeenCalledTimes(1));
    expect(invokeMock).toHaveBeenCalledWith("workgroup_members", {
      profile: "hub",
      wgId: "launch",
      connectionId: "local",
    });
    expect(invokeMock.mock.calls.some(([command]) => command === "read_file")).toBe(false);
    expect(screen.getByText("42 · $0.0042")).toBeInTheDocument();
  });
});
