import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const invokeMock = vi.fn();
const fetchWorkgroupTranscriptMock = vi.fn();
const listeners = {};

vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args) => invokeMock(...args),
}));
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(async (name, cb) => {
    listeners[name] = cb;
    return vi.fn();
  }),
}));
vi.mock("../lib/workgroup-fetch.js", () => ({
  fetchWorkgroupTranscript: (...args) => fetchWorkgroupTranscriptMock(...args),
}));
vi.mock("../hooks/useProfileDetail.js", () => ({
  useProfileDetail: () => ({ detail: null }),
}));

import WorkgroupView from "./WorkgroupView.jsx";
import styles from "./WorkgroupView.module.css";
import chipStyles from "../primitives/Chip.module.css";
import markerStyles from "../primitives/MarkerCard.module.css";

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
  pipelines: { setup: ["setup", "enrich"], "media-update": ["media-update", "media-qa"] },
  launch_pipeline: "setup",
  pipeline_mode: true,
};
const profiles = [{ name: "hub", accent: "#5588ff", pubkey_b64: "hub-pubkey" }];

const POSTS = [
  { seq: 40, from_pubkey: "hub-pubkey", body: "@pixel #task #setup go" },
  { seq: 41, from_pubkey: "hub-pubkey", body: "#done setup green" },
  { seq: 42, from_pubkey: "hub-pubkey", body: "@pixel #task #enrich go" },
];

let taskState = null;
let taskFail = false;

function tasksReply(state) {
  taskState = state;
  taskFail = false;
}

function tasksFail() {
  taskFail = true;
}

function phaseEl(slug) {
  return document.querySelector(`[data-phase="${slug}"]`);
}

function foldCalls() {
  return invokeMock.mock.calls.filter((c) => c[0] === "workgroup_tasks").length;
}

function poke() {
  listeners["daemon-event"]?.({
    payload: { frame: { event: "wg.post", data: { profile: "hub", wg_id: "launch" } } },
  });
}

beforeEach(() => {
  invokeMock.mockReset();
  taskState = null;
  taskFail = false;
  invokeMock.mockImplementation(async (cmd) => {
    if (cmd === "workgroup_tasks") {
      if (taskFail) throw new Error("daemon unreachable");
      return taskState;
    }
    return "";
  });
  fetchWorkgroupTranscriptMock.mockReset();
  fetchWorkgroupTranscriptMock.mockResolvedValue(POSTS);
});

describe("WorkgroupView pipeline strip", () => {
  it("labels the strip with the launch pipeline key and renders its phases", async () => {
    tasksReply({
      active: { slug: "enrich", title: "go", opened_seq: 42 },
      closed: [],
      blocked: null,
      pipeline_run: {
        pipeline: "setup",
        status: "running",
        started_seq: 40,
        current_phase: "enrich",
        phases: [
          { slug: "setup", state: "completed", seq: 41 },
          { slug: "enrich", state: "current", seq: 42 },
        ],
      },
    });

    render(<WorkgroupView workgroup={workgroup} profiles={profiles} connectionId="local" />);

    await waitFor(() => expect(screen.getByText("pipeline · setup")).toBeInTheDocument());
    expect(invokeMock).toHaveBeenCalledWith("workgroup_tasks", {
      profile: "hub",
      wgId: "launch",
      connectionId: "local",
    });
    expect(phaseEl("setup").dataset.phaseState).toBe("completed");
    expect(phaseEl("enrich").dataset.phaseState).toBe("current");
  });

  it("never renders the workgroup's declared launch chain when the run is another pipeline", async () => {
    tasksReply({
      active: { slug: "media-qa", title: "audit", opened_seq: 44 },
      closed: [],
      blocked: null,
      pipeline_run: {
        pipeline: "media-update",
        status: "running",
        started_seq: 43,
        current_phase: "media-qa",
        phases: [
          { slug: "media-update", state: "completed", seq: 43 },
          { slug: "media-qa", state: "current", seq: 44 },
        ],
      },
    });

    render(<WorkgroupView workgroup={workgroup} profiles={profiles} connectionId="local" />);

    await waitFor(() =>
      expect(screen.getByText("pipeline · media-update")).toBeInTheDocument(),
    );
    expect(screen.queryByText("pipeline · setup")).toBeNull();
    expect(phaseEl("setup")).toBeNull();
    expect(phaseEl("enrich")).toBeNull();
    expect(phaseEl("media-qa").dataset.phaseState).toBe("current");
  });

  it("a maintenance run replaces the launch run on refresh", async () => {
    tasksReply({
      active: null,
      closed: [],
      blocked: null,
      pipeline_run: {
        pipeline: "setup",
        status: "completed",
        started_seq: 40,
        current_phase: "enrich",
        phases: [
          { slug: "setup", state: "completed", seq: 41 },
          { slug: "enrich", state: "completed", seq: 43 },
        ],
      },
    });

    const { rerender } = render(
      <WorkgroupView
        workgroup={workgroup}
        profiles={profiles}
        connectionId="local"
        refreshCommandTick={1}
      />,
    );
    await waitFor(() => expect(screen.getByText("pipeline · setup")).toBeInTheDocument());
    expect(screen.getByText("completed")).toBeInTheDocument();

    tasksReply({
      active: { slug: "media-update", title: "swap photos", opened_seq: 50 },
      closed: [],
      blocked: null,
      pipeline_run: {
        pipeline: "media-update",
        status: "running",
        started_seq: 50,
        current_phase: "media-update",
        phases: [
          { slug: "media-update", state: "current", seq: 50 },
          { slug: "media-qa", state: "pending", seq: null },
        ],
      },
    });
    rerender(
      <WorkgroupView
        workgroup={workgroup}
        profiles={profiles}
        connectionId="local"
        refreshCommandTick={2}
      />,
    );

    await waitFor(() =>
      expect(screen.getByText("pipeline · media-update")).toBeInTheDocument(),
    );
    expect(screen.queryByText("pipeline · setup")).toBeNull();
    expect(screen.queryByText("completed")).toBeNull();
  });

  it("a repeated maintenance run resets completed phase state", async () => {
    tasksReply({
      active: null,
      closed: [],
      blocked: null,
      pipeline_run: {
        pipeline: "media-update",
        status: "completed",
        started_seq: 50,
        current_phase: "media-qa",
        phases: [
          { slug: "media-update", state: "completed", seq: 51 },
          { slug: "media-qa", state: "completed", seq: 53 },
        ],
      },
    });
    const { rerender } = render(
      <WorkgroupView
        workgroup={workgroup}
        profiles={profiles}
        connectionId="local"
        refreshCommandTick={1}
      />,
    );
    await waitFor(() => expect(phaseEl("media-qa").dataset.phaseState).toBe("completed"));

    tasksReply({
      active: { slug: "media-update", title: "again", opened_seq: 60 },
      closed: [],
      blocked: null,
      pipeline_run: {
        pipeline: "media-update",
        status: "running",
        started_seq: 60,
        current_phase: "media-update",
        phases: [
          { slug: "media-update", state: "current", seq: 60 },
          { slug: "media-qa", state: "pending", seq: null },
        ],
      },
    });
    rerender(
      <WorkgroupView
        workgroup={workgroup}
        profiles={profiles}
        connectionId="local"
        refreshCommandTick={2}
      />,
    );

    await waitFor(() => expect(phaseEl("media-qa").dataset.phaseState).toBe("pending"));
    expect(phaseEl("media-update").dataset.phaseState).toBe("current");
  });

  it("an ad-hoc task opened after a finished run drops the strip", async () => {
    tasksReply({
      active: null,
      closed: [{ slug: "enrich", result: "enrich green", closed_seq: 42, blocked: false }],
      blocked: null,
      pipeline_run: {
        pipeline: "setup",
        status: "completed",
        started_seq: 40,
        current_phase: "enrich",
        phases: [
          { slug: "setup", state: "completed", seq: 41 },
          { slug: "enrich", state: "completed", seq: 42 },
        ],
      },
    });
    render(<WorkgroupView workgroup={workgroup} profiles={profiles} connectionId="local" />);
    await waitFor(() => expect(screen.getByText("pipeline · setup")).toBeInTheDocument());

    tasksReply({
      active: { slug: "hotfix", title: "one-off", opened_seq: 70 },
      closed: [{ slug: "enrich", result: "enrich green", closed_seq: 42, blocked: false }],
      blocked: null,
      pipeline_run: null,
    });
    poke();

    await waitFor(() => expect(screen.queryByText(/^pipeline · /)).toBeNull());
    expect(phaseEl("setup")).toBeNull();
    expect(screen.getByText("one-off")).toBeInTheDocument();
  });

  it("an idle launchless workgroup shows no strip before its first trigger", async () => {
    tasksReply({ active: null, closed: [], blocked: null, pipeline_run: null });
    render(
      <WorkgroupView
        workgroup={{
          ...workgroup,
          launch_pipeline: null,
          pipelines: { "media-update": ["media-update", "media-qa"] },
        }}
        profiles={profiles}
        connectionId="local"
      />,
    );

    await waitFor(() => expect(invokeMock).toHaveBeenCalledWith("workgroup_tasks", expect.anything()));
    expect(screen.queryByText(/^pipeline · /)).toBeNull();
  });

  it("a blocked run keeps its phase current-but-blocked and banners the daemon reason", async () => {
    tasksReply({
      active: null,
      closed: [{ slug: "enrich", result: "BLOCKED enrich · no source photos", closed_seq: 43, blocked: true }],
      blocked: { slug: "enrich", reason: "BLOCKED enrich · no source photos" },
      pipeline_run: {
        pipeline: "setup",
        status: "blocked",
        started_seq: 40,
        current_phase: "enrich",
        phases: [
          { slug: "setup", state: "completed", seq: 41 },
          { slug: "enrich", state: "current", seq: 43 },
        ],
      },
    });
    render(<WorkgroupView workgroup={workgroup} profiles={profiles} connectionId="local" />);

    await waitFor(() => expect(screen.getByText("Blocked at #enrich.")).toBeInTheDocument());
    expect(screen.getByText(/no source photos/)).toBeInTheDocument();
    expect(phaseEl("enrich").dataset.phaseState).toBe("blocked");
    expect(screen.getByText("blocked")).toBeInTheDocument();

    const blocked = phaseEl("enrich");
    const completed = phaseEl("setup");
    expect(blocked.querySelector(`.${chipStyles.errorState}`)).not.toBeNull();
    expect(completed.querySelector(`.${chipStyles.errorState}`)).toBeNull();
    expect(blocked.querySelector("svg circle")).not.toBeNull();
    expect(completed.querySelector("svg circle")).toBeNull();
    expect(completed.querySelectorAll("svg path")).toHaveLength(1);
  });

  it("a between run says so in words and leaves no current phase", async () => {
    tasksReply({
      active: null,
      closed: [{ slug: "setup", result: "setup green", closed_seq: 41, blocked: false }],
      blocked: null,
      pipeline_run: {
        pipeline: "setup",
        status: "between",
        started_seq: 40,
        current_phase: "setup",
        phases: [
          { slug: "setup", state: "completed", seq: 41 },
          { slug: "enrich", state: "pending", seq: null },
        ],
      },
    });
    render(<WorkgroupView workgroup={workgroup} profiles={profiles} connectionId="local" />);

    await waitFor(() => expect(screen.getByText("between phases")).toBeInTheDocument());
    expect(screen.queryByText("between")).toBeNull();
    expect(document.querySelector('[data-phase-state="current"]')).toBeNull();
    expect(phaseEl("enrich").querySelector("svg")).toBeNull();
    expect(phaseEl("enrich")).not.toHaveClass(styles.phaseSkipped);
  });

  it("a skipped middle phase is visually distinct from a completed and a pending one", async () => {
    tasksReply({
      active: { slug: "qa", title: "audit", opened_seq: 44 },
      closed: [
        { slug: "setup", result: "setup green", closed_seq: 41, blocked: false },
        { slug: "enrich", result: "skipped · nothing to enrich", closed_seq: 42, blocked: false },
      ],
      blocked: null,
      pipeline_run: {
        pipeline: "setup",
        status: "running",
        started_seq: 40,
        current_phase: "qa",
        phases: [
          { slug: "setup", state: "completed", seq: 41 },
          { slug: "enrich", state: "skipped", seq: 42 },
          { slug: "qa", state: "current", seq: 44 },
        ],
      },
    });
    render(
      <WorkgroupView
        workgroup={{ ...workgroup, pipelines: { setup: ["setup", "enrich", "qa"] } }}
        profiles={profiles}
        connectionId="local"
      />,
    );

    await waitFor(() => expect(phaseEl("qa")).not.toBeNull());
    const completed = phaseEl("setup");
    const skipped = phaseEl("enrich");
    expect(skipped.dataset.phaseState).toBe("skipped");
    expect(skipped).toHaveClass(styles.phaseSkipped);
    expect(completed).not.toHaveClass(styles.phaseSkipped);
    expect(skipped.querySelectorAll("svg path")).toHaveLength(2);
    expect(skipped.querySelector("svg circle")).toBeNull();
    expect(completed.querySelectorAll("svg path")).toHaveLength(1);
    expect(phaseEl("qa").querySelector("svg")).toBeNull();
  });

  it("a chain that finishes by skipping its last phase reads completed", async () => {
    tasksReply({
      active: null,
      closed: [
        { slug: "setup", result: "setup green", closed_seq: 41, blocked: false },
        { slug: "enrich", result: "skipped · no photos to add", closed_seq: 42, blocked: false },
      ],
      blocked: null,
      pipeline_run: {
        pipeline: "setup",
        status: "completed",
        started_seq: 40,
        current_phase: "enrich",
        phases: [
          { slug: "setup", state: "completed", seq: 41 },
          { slug: "enrich", state: "skipped", seq: 42 },
        ],
      },
    });
    render(<WorkgroupView workgroup={workgroup} profiles={profiles} connectionId="local" />);

    await waitFor(() => expect(screen.getByText("completed")).toBeInTheDocument());
    expect(phaseEl("enrich")).toHaveClass(styles.phaseSkipped);
    expect(phaseEl("enrich").querySelectorAll("svg path")).toHaveLength(2);
    expect(document.querySelector('[data-phase-state="current"]')).toBeNull();
  });

  it("a seq outside the loaded transcript window says why it cannot be opened", async () => {
    tasksReply({
      active: { slug: "enrich", title: "go", opened_seq: 42 },
      closed: [],
      blocked: null,
      pipeline_run: {
        pipeline: "setup",
        status: "running",
        started_seq: 3,
        current_phase: "enrich",
        phases: [
          { slug: "setup", state: "completed", seq: 4 },
          { slug: "enrich", state: "current", seq: 42 },
        ],
      },
    });
    render(<WorkgroupView workgroup={workgroup} profiles={profiles} connectionId="local" />);

    await waitFor(() => expect(phaseEl("setup")).not.toBeNull());
    expect(phaseEl("setup").querySelector("button")).toBeNull();
    expect(phaseEl("setup").getAttribute("aria-disabled")).toBe("true");
    expect(phaseEl("setup").getAttribute("title")).toMatch(/outside the loaded history/);
    expect(phaseEl("enrich").querySelector("button")).not.toBeNull();
    expect(phaseEl("enrich").getAttribute("aria-disabled")).toBeNull();
    expect(phaseEl("enrich").getAttribute("title")).toBeNull();
  });

  it("a phase that has not opened yet says so instead of staying silent", async () => {
    tasksReply({
      active: null,
      closed: [],
      blocked: null,
      pipeline_run: {
        pipeline: "setup",
        status: "between",
        started_seq: 40,
        current_phase: "setup",
        phases: [
          { slug: "setup", state: "completed", seq: 41 },
          { slug: "enrich", state: "pending", seq: null },
        ],
      },
    });
    render(<WorkgroupView workgroup={workgroup} profiles={profiles} connectionId="local" />);

    await waitFor(() => expect(phaseEl("enrich")).not.toBeNull());
    expect(phaseEl("enrich").getAttribute("title")).toMatch(/has not opened yet/);
    expect(phaseEl("enrich").getAttribute("aria-disabled")).toBe("true");
  });

  it("re-reads the canonical state after a workgroup_changed trigger event", async () => {
    tasksReply({ active: null, closed: [], blocked: null, pipeline_run: null });
    render(<WorkgroupView workgroup={workgroup} profiles={profiles} connectionId="local" />);
    await waitFor(() => expect(foldCalls()).toBe(1));

    tasksReply({
      active: { slug: "media-update", title: "swap photos", opened_seq: 50 },
      closed: [],
      blocked: null,
      pipeline_run: {
        pipeline: "media-update",
        status: "running",
        started_seq: 50,
        current_phase: "media-update",
        phases: [
          { slug: "media-update", state: "current", seq: 50 },
          { slug: "media-qa", state: "pending", seq: null },
        ],
      },
    });
    listeners["daemon-event"]({
      payload: {
        connection_id: "local",
        frame: {
          event: "workgroup_changed",
          data: { profile: "hub", wg_id: "launch", action: "trigger" },
        },
      },
    });

    await waitFor(() =>
      expect(screen.getByText("pipeline · media-update")).toBeInTheDocument(),
    );
  });
});

describe("WorkgroupView canonical state availability", () => {
  it("keeps the last canonical state and marks it stale when the fold call fails", async () => {
    tasksFail();
    render(
      <WorkgroupView
        workgroup={workgroup}
        profiles={profiles}
        connectionId={null}
      />,
    );
    await waitFor(() => expect(screen.getByTestId("pipeline-stale")).toBeTruthy());
    expect(phaseEl("setup")).toBeNull();
  });

  it("a blocked run stays on screen with a stale marker rather than vanishing", async () => {
    tasksReply({
      active: null,
      closed: [],
      blocked: { slug: "enrich", reason: "BLOCKED enrich · no source photos" },
      pipeline_run: {
        pipeline: "setup",
        status: "blocked",
        started_seq: 40,
        current_phase: "enrich",
        phases: [
          { slug: "setup", state: "completed", seq: 41 },
          { slug: "enrich", state: "current", seq: 42 },
        ],
      },
    });
    render(
      <WorkgroupView
        workgroup={workgroup}
        profiles={profiles}
        connectionId={null}
      />,
    );
    await waitFor(() => expect(phaseEl("enrich")?.dataset.phaseState).toBe("blocked"));
    expect(screen.queryByTestId("pipeline-stale")).toBeNull();

    tasksFail();
    poke();
    await waitFor(() => expect(screen.getByTestId("pipeline-stale")).toBeTruthy());
    expect(phaseEl("enrich")?.dataset.phaseState).toBe("blocked");
  });

  it("drops the stale marker as soon as the fold answers again", async () => {
    tasksFail();
    render(
      <WorkgroupView
        workgroup={workgroup}
        profiles={profiles}
        connectionId={null}
      />,
    );
    await waitFor(() => expect(screen.getByTestId("pipeline-stale")).toBeTruthy());

    tasksReply({
      active: null,
      closed: [],
      blocked: null,
      pipeline_run: {
        pipeline: "setup",
        status: "completed",
        started_seq: 40,
        current_phase: "enrich",
        phases: [
          { slug: "setup", state: "completed", seq: 41 },
          { slug: "enrich", state: "completed", seq: 42 },
        ],
      },
    });
    poke();

    await waitFor(() => expect(screen.queryByTestId("pipeline-stale")).toBeNull());
    expect(phaseEl("setup")).not.toBeNull();
  });
});

describe("WorkgroupView task pill", () => {
  it("reads the canonical fold, never the loaded transcript tail", async () => {
    fetchWorkgroupTranscriptMock.mockResolvedValue([
      { seq: 900, from_pubkey: "hub-pubkey", body: "carry on" },
    ]);
    tasksReply({
      active: { slug: "media-qa", title: "Audit the new photo set", opened_seq: 901 },
      closed: [
        { slug: "setup", result: "setup green", closed_seq: 41, blocked: false },
        { slug: "enrich", result: "skipped · nothing to enrich", closed_seq: 42, blocked: false },
      ],
      blocked: null,
      pipeline_run: null,
    });
    render(<WorkgroupView workgroup={workgroup} profiles={profiles} connectionId="local" />);

    await waitFor(() =>
      expect(screen.getByText("Audit the new photo set")).toBeInTheDocument(),
    );
    expect(screen.queryByText("No tasks yet")).toBeNull();
    expect(screen.getByText("2/3")).toBeInTheDocument();
  });

  it("a closed-but-blocked history reads blocked, never resolved", async () => {
    tasksReply({
      active: null,
      closed: [
        { slug: "setup", result: "setup green", closed_seq: 41, blocked: false },
        { slug: "enrich", result: "BLOCKED enrich · no source photos", closed_seq: 43, blocked: true },
      ],
      blocked: { slug: "enrich", reason: "BLOCKED enrich · no source photos" },
      pipeline_run: null,
    });
    render(<WorkgroupView workgroup={workgroup} profiles={profiles} connectionId="local" />);

    await waitFor(() => expect(screen.getByText("Blocked at #enrich")).toBeInTheDocument());
    expect(screen.queryByText("All tasks resolved")).toBeNull();
  });

  it("falls back to the transcript derivation when the fold is unavailable", async () => {
    tasksFail();
    render(<WorkgroupView workgroup={workgroup} profiles={profiles} connectionId="local" />);

    await waitFor(() => expect(screen.getByTestId("pipeline-stale")).toBeTruthy());
    const header = within(document.querySelector("header"));
    expect(header.getByText("go")).toBeInTheDocument();
    expect(header.getByText("1/2")).toBeInTheDocument();
    expect(screen.queryByText("No tasks yet")).toBeNull();
  });
});

describe("WorkgroupView close markers", () => {
  it("renders a skipped and a BLOCKED close distinctly from a green one", async () => {
    fetchWorkgroupTranscriptMock.mockResolvedValue([
      { seq: 40, from_pubkey: "hub-pubkey", body: "@pixel #task #setup go" },
      { seq: 41, from_pubkey: "hub-pubkey", body: "#done setup green" },
      { seq: 42, from_pubkey: "hub-pubkey", body: "@pixel #task #enrich go" },
      { seq: 43, from_pubkey: "hub-pubkey", body: "#done skipped · nothing to enrich" },
      { seq: 44, from_pubkey: "hub-pubkey", body: "@pixel #task #qa go" },
      { seq: 45, from_pubkey: "hub-pubkey", body: "Everything looks fine\n#done BLOCKED · the template cannot build" },
    ]);
    tasksReply({
      active: null,
      closed: [
        { slug: "setup", result: "setup green", closed_seq: 41, blocked: false },
        { slug: "enrich", result: "skipped · nothing to enrich", closed_seq: 43, blocked: false },
        { slug: "qa", result: "BLOCKED · the template cannot build", closed_seq: 45, blocked: true },
      ],
      blocked: { slug: "qa", reason: "BLOCKED qa · the template cannot build" },
      pipeline_run: null,
    });
    render(<WorkgroupView workgroup={workgroup} profiles={profiles} connectionId="local" />);

    await waitFor(() => expect(document.getElementById("task-45")).not.toBeNull());
    const green = document.getElementById("task-41");
    const skipped = document.getElementById("task-43");
    const blocked = document.getElementById("task-45");

    expect(green.querySelector(".ey")).toHaveTextContent(/^DONE$/);
    expect(skipped.querySelector(".ey")).toHaveTextContent(/^SKIPPED$/);
    expect(blocked.querySelector(".ey")).toHaveTextContent(/^BLOCKED$/);

    expect(green).not.toHaveClass(markerStyles.closeSkipped);
    expect(green).not.toHaveClass(markerStyles.closeBlocked);
    expect(skipped).toHaveClass(markerStyles.closeSkipped);
    expect(blocked).toHaveClass(markerStyles.closeBlocked);

    expect(green.querySelector(".ey svg circle")).toBeNull();
    expect(blocked.querySelector(".ey svg circle")).not.toBeNull();
    expect(skipped.querySelectorAll(".ey svg path")).toHaveLength(2);
  });
});

const HUB_WG = {
  ...workgroup,
  is_hub: true,
  phase_map: {
    setup: { owner: "pixel", task: "Wire the skeleton" },
    "media-update": { owner: "mira", task: "Swap in the new photo set" },
  },
};

const IDLE = { active: null, closed: [], blocked: null, pipeline_run: null };
