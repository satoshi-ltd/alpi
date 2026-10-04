import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
    await waitFor(() => expect(screen.getByText("No posts yet")).toBeInTheDocument());
    expect(screen.getByText("Direct @hub to open a #task.")).toBeInTheDocument();
    expect(container.querySelector("[data-fold='honeycomb']")).toBeTruthy();
  });

  it("drops a deleted workgroup when its transcript returns not-found", async () => {
    const onGone = vi.fn();
    fetchWorkgroupTranscriptMock.mockRejectedValueOnce(
      "alp -32004: not-found — no workgroup 'launch'",
    );

    render(
      <WorkgroupView
        workgroup={workgroup}
        profiles={profiles}
        connectionId="local"
        onGone={onGone}
      />,
    );

    await waitFor(() => {
      expect(onGone).toHaveBeenCalledWith("local", "hub", "launch");
    });
  });

  it("shows a skeleton while the transcript loads, never a blank body", () => {
    fetchWorkgroupTranscriptMock.mockReturnValueOnce(new Promise(() => {}));
    const { container } = render(
      <WorkgroupView workgroup={workgroup} profiles={profiles} connectionId="local" />,
    );
    expect(container.querySelector(".anim-fade[aria-hidden='true']")).toBeTruthy();
    expect(screen.queryByText("No posts yet")).toBeNull();
  });

  it("names a failed load and retries it instead of pretending the workgroup is empty", async () => {
    fetchWorkgroupTranscriptMock.mockRejectedValueOnce(new Error("read timeout"));
    render(<WorkgroupView workgroup={workgroup} profiles={profiles} connectionId="local" />);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Couldn't load this workgroup"));
    expect(screen.queryByText("No posts yet")).toBeNull();
    fetchWorkgroupTranscriptMock.mockResolvedValueOnce([]);
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(screen.getByText("No posts yet")).toBeInTheDocument());
  });
});
