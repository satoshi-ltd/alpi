import { render, screen, waitFor } from "@testing-library/react";
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

const workgroup = { id: "launch", profile: "hub", hub_id: "hub", paused: false, auto_read: false, members: 1 };
const profiles = [{ name: "hub", accent: "#5588ff", pubkey_b64: "hub-pubkey" }];

beforeEach(() => {
  invokeMock.mockReset();
  invokeMock.mockResolvedValue("");
  fetchWorkgroupTranscriptMock.mockReset();
  fetchWorkgroupTranscriptMock.mockResolvedValue([]);
});

describe("WorkgroupView empty state", () => {
  it("renders the shared empty-chat banner (llama + hint) when there are no posts", async () => {
    const { container } = render(
      <WorkgroupView workgroup={workgroup} profiles={profiles} connectionId="local" />,
    );
    await waitFor(() => expect(screen.getByText("no posts yet")).toBeInTheDocument());
    expect(screen.getByText(/direct @hub to open a #task/)).toBeInTheDocument();
    expect(container.querySelector("svg")).toBeTruthy();
  });
});
