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
import { nameTone } from "../../../common/name.mjs";
import { palettes } from "../../../common/tokens.mjs";

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
    expect(container.querySelector("[data-shape='honeycomb']")).toBeTruthy();
  });

  it("lights the empty-state honeycomb in the colour of the profile at work, like the header", async () => {
    invokeMock.mockImplementation((cmd) => Promise.resolve(cmd === "workgroup_tasks" ? {
      active: { slug: "enrich", title: "go", opened_seq: 1 }, closed: [], blocked: null,
      pipeline_run: { pipeline: "setup", status: "running", current_phase: "enrich", phases: [{ slug: "setup", state: "completed", seq: 1 }, { slug: "enrich", state: "current", seq: 2 }, { slug: "qa", state: "pending", seq: null }] },
    } : ""));
    const running = { ...workgroup, pipeline_status: "running", pipelines: { setup: ["setup", "enrich", "qa"] }, phase_map: { enrich: { owner: "@Pixel" } } };
    const { container } = render(<WorkgroupView workgroup={running} profiles={[...profiles, { name: "pixel", accent: "#f36a8a" }]} connectionId="local" />);
    await waitFor(() => expect(screen.getByText("No posts yet")).toBeInTheDocument());
    await waitFor(() => expect(container.querySelectorAll("[data-shape='honeycomb'][data-state='running']")).toHaveLength(2));
    for (const mark of container.querySelectorAll("[data-shape='honeycomb']")) {
      expect(mark.style.getPropertyValue("--wg-lit-light")).toBe(nameTone("#f36a8a", palettes.light.bgPane));
    }
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
