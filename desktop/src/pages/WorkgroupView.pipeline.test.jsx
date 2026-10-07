import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

import WorkgroupView, { _resetTaskStateCache } from "./WorkgroupView.jsx";
import styles from "./WorkgroupView.module.css";
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
  _resetTaskStateCache();
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

describe("WorkgroupView working heartbeats", () => {
  it("labels every #working card WORKING, even once a later heartbeat supersedes it", async () => {
    fetchWorkgroupTranscriptMock.mockResolvedValue([
      ...POSTS,
      { seq: 43, from_pubkey: "quill-pubkey", body: "#working" },
      { seq: 44, from_pubkey: "quill-pubkey", body: "#working half written; next pages (continuation)" },
    ]);
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

    await waitFor(() => expect(screen.getAllByText("WORKING")).toHaveLength(2));
    expect(screen.queryByText("WORK")).toBeNull();
  });
});

describe("WorkgroupView pipeline strip", () => {
  it("shows phase-sized placeholder chips with several pipelines until the first canonical fold arrives", async () => {
    let resolveTasks;
    invokeMock.mockImplementation((cmd) => {
      if (cmd === "workgroup_tasks") {
        return new Promise((resolve) => {
          resolveTasks = resolve;
        });
      }
      return Promise.resolve("");
    });

    render(<WorkgroupView workgroup={{ ...workgroup, pipeline_status: "running" }} profiles={profiles} connectionId="local" />);

    const loading = screen.getByTestId("pipeline-loading");
    expect(loading.querySelectorAll("[data-phase-placeholder]")).toHaveLength(2);
    expect(within(loading).getByRole("status", { name: "Loading the pipeline" })).toBeInTheDocument();
    expect(loading.textContent).not.toMatch(/Loading/);
    expect(document.querySelector("[data-phase]")).toBeNull();
    resolveTasks({
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

    await waitFor(() => expect(phaseEl("setup")).not.toBeNull());
    expect(screen.queryByTestId("pipeline-loading")).toBeNull();
  });

  it("draws a single pipeline from the row at once, every phase pending with its owner, then fills it in place", async () => {
    let resolveTasks;
    invokeMock.mockImplementation((cmd) => {
      if (cmd === "workgroup_tasks") return new Promise((resolve) => { resolveTasks = resolve; });
      return Promise.resolve("");
    });
    const single = {
      ...workgroup,
      pipeline_status: "running",
      pipelines: { setup: ["setup", "enrich", "qa"] },
      phase_map: { setup: { owner: "hub" }, enrich: { owner: "pixel" }, qa: { owner: "hub" } },
    };

    render(<WorkgroupView workgroup={single} profiles={profiles} connectionId="local" />);

    const strip = screen.getByTestId("pipeline-strip");
    expect(strip.hasAttribute("data-pending")).toBe(true);
    expect(screen.queryByTestId("pipeline-loading")).toBeNull();
    expect(["setup", "enrich", "qa"].map((slug) => phaseEl(slug).dataset.state)).toEqual(["pending", "pending", "pending"]);
    expect(phaseEl("setup").querySelector("[data-fold]")).not.toBeNull();
    expect(phaseEl("enrich").querySelector("[data-fold]").dataset.unfolded).toBe("");
    expect(phaseEl("setup").querySelector("polygon").getAttribute("class") ?? "").toBe("");
    expect(strip.textContent).not.toMatch(/Loading/);
    expect(strip.textContent).toContain("pipeline");

    resolveTasks({
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
          { slug: "qa", state: "pending", seq: null },
        ],
      },
    });

    await waitFor(() => expect(phaseEl("setup").dataset.state).toBe("completed"));
    expect(screen.getByTestId("pipeline-strip")).toBe(strip);
    expect(strip.hasAttribute("data-pending")).toBe(false);
    expect(phaseEl("enrich").dataset.state).toBe("current");
    expect(phaseEl("qa").dataset.state).toBe("pending");
  });

  it.each([
    ["an idle workgroup with no run", { pipeline_status: null }],
    ["a queued item without a run", { pipeline_status: "queued" }],
    ["an older daemon's row without the field", {}],
  ])("%s draws no pending strip before or after the reply", async (_, extra) => {
    let resolveTasks;
    invokeMock.mockImplementation((cmd) => {
      if (cmd === "workgroup_tasks") return new Promise((resolve) => { resolveTasks = resolve; });
      return Promise.resolve("");
    });
    for (const pipelines of [{ setup: ["setup", "enrich"] }, workgroup.pipelines]) {
      const { unmount } = render(
        <WorkgroupView workgroup={{ ...workgroup, ...extra, pipelines }} profiles={profiles} connectionId="local" />,
      );
      expect(screen.queryByTestId("pipeline-strip")).toBeNull();
      expect(screen.queryByTestId("pipeline-loading")).toBeNull();
      expect(document.querySelector("[data-phase]")).toBeNull();
      await act(async () => resolveTasks({ active: null, closed: [], blocked: null, pipeline_run: null }));
      expect(screen.queryByTestId("pipeline-strip")).toBeNull();
      expect(screen.queryByTestId("pipeline-loading")).toBeNull();
      expect(document.querySelector("[data-phase]")).toBeNull();
      unmount();
      _resetTaskStateCache();
    }
  });

  it.each([
    ["running", "chain", "placeholders"],
    ["between", "chain", "placeholders"],
    ["blocked", "placeholders", "placeholders"],
    ["completed", "placeholders", "placeholders"],
    ["queued", "nothing", "nothing"],
    [null, "nothing", "nothing"],
    [undefined, "nothing", "nothing"],
  ])("before the reply a row with status %s draws %s for one pipeline and %s for several", (status, single, several) => {
    invokeMock.mockImplementation((cmd) => (cmd === "workgroup_tasks" ? new Promise(() => {}) : Promise.resolve("")));
    const drawn = () => (
      document.querySelector("[data-phase]") ? "chain"
        : document.querySelector("[data-phase-placeholder]") ? "placeholders" : "nothing"
    );
    const row = { ...workgroup, pipeline_status: status };
    if (status === undefined) delete row.pipeline_status;
    const one = render(<WorkgroupView workgroup={{ ...row, pipelines: { setup: ["setup", "enrich"] } }} profiles={profiles} connectionId="local" />);
    expect(drawn()).toBe(single);
    if (single === "chain") expect(phaseEl("setup").dataset.state).toBe("pending");
    one.unmount();
    render(<WorkgroupView workgroup={row} profiles={profiles} connectionId="local" />);
    expect(drawn()).toBe(several);
  });

  it.each([{}, null, { setup: [] }])("a running row with no declared pipeline (%j) draws nothing before the reply", (pipelines) => {
    invokeMock.mockImplementation((cmd) => (cmd === "workgroup_tasks" ? new Promise(() => {}) : Promise.resolve("")));
    render(<WorkgroupView workgroup={{ ...workgroup, pipeline_status: "running", pipelines }} profiles={profiles} connectionId="local" />);
    expect(screen.queryByTestId("pipeline-loading")).toBeNull();
    expect(screen.queryByTestId("pipeline-strip")).toBeNull();
    expect(document.querySelector("[data-phase], [data-phase-placeholder]")).toBeNull();
  });

  it.each([
    ["one pipeline", { setup: ["setup", "enrich"] }],
    ["several pipelines", workgroup.pipelines],
  ])("draws nothing beside the stale banner once the daemon fails to answer, with %s", async (_, pipelines) => {
    tasksFail();
    render(<WorkgroupView workgroup={{ ...workgroup, pipeline_status: "running", pipelines }} profiles={profiles} connectionId="local" />);
    await screen.findByTestId("pipeline-stale");
    expect(screen.queryByTestId("pipeline-loading")).toBeNull();
    expect(screen.queryByTestId("pipeline-strip")).toBeNull();
    expect(screen.queryByRole("status", { name: "Loading the pipeline" })).toBeNull();
    expect(document.querySelector("[data-phase], [data-phase-placeholder]")).toBeNull();
  });

  it("keeps the last valid flow visible while a remounted view refreshes", async () => {
    const state = {
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
    };
    tasksReply(state);
    const first = render(
      <WorkgroupView workgroup={workgroup} profiles={profiles} connectionId="local" />,
    );
    await waitFor(() => expect(phaseEl("setup")).not.toBeNull());
    first.unmount();

    invokeMock.mockImplementation((cmd) => (
      cmd === "workgroup_tasks" ? new Promise(() => {}) : Promise.resolve("")
    ));
    render(<WorkgroupView workgroup={workgroup} profiles={profiles} connectionId="local" />);

    expect(phaseEl("setup")).not.toBeNull();
    expect(screen.queryByTestId("pipeline-loading")).toBeNull();
  });

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

    await waitFor(() => expect(phaseEl("setup")).not.toBeNull());
    expect(invokeMock).toHaveBeenCalledWith("workgroup_tasks", {
      profile: "hub",
      wgId: "launch",
      connectionId: "local",
    });
    expect(phaseEl("setup").dataset.state).toBe("completed");
    expect(phaseEl("enrich").dataset.state).toBe("current");
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

    await waitFor(() => expect(phaseEl("media-update")).not.toBeNull());
    expect(phaseEl("setup")).toBeNull();
    expect(phaseEl("enrich")).toBeNull();
    expect(phaseEl("media-qa").dataset.state).toBe("current");
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
    await waitFor(() => expect(phaseEl("setup")).not.toBeNull());
    expect(document.querySelector(`.${styles.pipeline}`).children).toHaveLength(2);

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

    const bar = document.querySelector(".refresh-bar");
    expect(bar).not.toBeNull();
    expect(bar.getAttribute("style")).toBeNull();
    expect(bar.outerHTML).not.toContain(profiles[0].accent);
    await waitFor(() => expect(phaseEl("media-update")).not.toBeNull());
    expect(phaseEl("enrich")).toBeNull();
    expect(document.querySelector('[data-phase][data-state="completed"]')).toBeNull();
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
    await waitFor(() => expect(phaseEl("media-qa").dataset.state).toBe("completed"));

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

    await waitFor(() => expect(phaseEl("media-qa").dataset.state).toBe("pending"));
    expect(phaseEl("media-update").dataset.state).toBe("current");
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
    await waitFor(() => expect(phaseEl("setup")).not.toBeNull());

    tasksReply({
      active: { slug: "hotfix", title: "one-off", opened_seq: 70 },
      closed: [{ slug: "enrich", result: "enrich green", closed_seq: 42, blocked: false }],
      blocked: null,
      pipeline_run: null,
    });
    poke();

    await waitFor(() => expect(document.querySelector("[data-phase]")).toBeNull());
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
    expect(document.querySelector("[data-phase]")).toBeNull();
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
    expect(screen.getByText("Blocked at #enrich.").closest("span")).toHaveTextContent(/no source photos/);
    expect(phaseEl("enrich").dataset.state).toBe("blocked");
    expect(phaseEl("enrich")).toHaveAccessibleName(/blocked/);
    expect(phaseEl("enrich").textContent).toBe("#enrich");
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

    await waitFor(() => expect(phaseEl("setup").dataset.state).toBe("completed"));
    expect(document.querySelector(`.${styles.pipeline}`).children).toHaveLength(2);
    expect(screen.queryByText("between")).toBeNull();
    expect(document.querySelector('[data-phase][data-state="current"]')).toBeNull();
    expect(phaseEl("enrich").querySelector("svg")).toBeNull();
    expect(phaseEl("enrich").textContent).toBe("#enrich");
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
    expect(skipped.dataset.state).toBe("skipped");
    expect(skipped).toHaveAccessibleName(/skipped/);
    expect(completed.dataset.state).toBe("completed");
    expect(completed).toHaveAccessibleName(/completed/);
    expect(phaseEl("qa")).toHaveAccessibleName(/running/);
    expect([completed, skipped, phaseEl("qa")].map((el) => el.textContent)).toEqual(["#setup", "#enrich", "#qa"]);
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

    await waitFor(() => expect(phaseEl("enrich").dataset.state).toBe("skipped"));
    expect(document.querySelector(`.${styles.pipeline}`).children).toHaveLength(2);
    expect(phaseEl("enrich").dataset.state).toBe("skipped");
    expect(document.querySelector('[data-phase][data-state="current"]')).toBeNull();
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
    expect(phaseEl("setup").tagName).toBe("SPAN");
    expect(phaseEl("setup").getAttribute("aria-disabled")).toBe("true");
    expect(phaseEl("setup").closest(".ds-tip")).toHaveTextContent(/outside the loaded history/);
    expect(phaseEl("enrich").tagName).toBe("BUTTON");
    expect(phaseEl("enrich").getAttribute("aria-disabled")).toBeNull();
    expect(phaseEl("enrich").closest(".ds-tip")).toHaveTextContent(/Click to jump to the post/);
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
    expect(phaseEl("enrich").closest(".ds-tip")).toHaveTextContent(/has not opened yet/);
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

    await waitFor(() => expect(phaseEl("media-update")).not.toBeNull());
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
    await waitFor(() => expect(phaseEl("enrich")?.dataset.state).toBe("blocked"));
    expect(screen.queryByTestId("pipeline-stale")).toBeNull();

    tasksFail();
    poke();
    await waitFor(() => expect(screen.getByTestId("pipeline-stale")).toBeTruthy());
    expect(phaseEl("enrich")?.dataset.state).toBe("blocked");
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

describe("WorkgroupView pipeline strip owners", () => {
  const owned = {
    ...workgroup,
    phase_map: { setup: { owner: "pixel", task: "initialise the project" }, enrich: { owner: "scout", task: "enrich the brief" } },
  };
  const crew = [
    ...profiles,
    { name: "pixel", accent: "#119988", fold: "rocket" },
    { name: "scout", accent: "#cc4422", fold: "house" },
    { name: "lingua", accent: "#bb2299", fold: "plane" },
  ];
  const running = (active) => ({
    active,
    closed: [],
    blocked: null,
    pipeline_run: {
      pipeline: "setup",
      status: "running",
      started_seq: 40,
      current_phase: "enrich",
      phases: [
        { slug: "setup", state: "completed", seq: 41, cost: { usd: 0.02, tokens: 8310 } },
        { slug: "enrich", state: "current", seq: 42 },
      ],
    },
  });

  it("draws each phase with its declared owner and the header counts the same phases as the strip", async () => {
    tasksReply(running({ slug: "enrich", title: "go", opened_seq: 42, assignees: ["scout"] }));
    render(<WorkgroupView workgroup={owned} profiles={crew} connectionId="local" />);

    await waitFor(() => expect(phaseEl("enrich")).not.toBeNull());
    expect(phaseEl("setup").querySelector('[data-fold="rocket"]')).not.toBeNull();
    expect(phaseEl("enrich").querySelector('[data-fold="house"]')).not.toBeNull();
    expect(within(phaseEl("enrich")).queryByText(/→/)).toBeNull();
    const trigger = document.querySelector("[data-phase-trigger]");
    expect(trigger).toHaveTextContent("#enrich");
    expect(trigger).toHaveTextContent("@scout");
    expect(trigger).toHaveTextContent("1 of 2");
    expect(phaseEl("setup").closest(".ds-tip")).toHaveTextContent("initialise the project");
    expect(phaseEl("setup").closest(".ds-tip")).toHaveTextContent("$0.02 · 8,310 tokens");
  });

  it("names the member a routed repair is addressed to, on the chip and in the header", async () => {
    tasksReply(running({ slug: "enrich", title: "restore the fr strings", opened_seq: 42, assignees: ["lingua"] }));
    render(<WorkgroupView workgroup={owned} profiles={crew} connectionId="local" />);

    await waitFor(() => expect(within(phaseEl("enrich")).getByText("@lingua")).toBeInTheDocument());
    expect(phaseEl("enrich").querySelector('[data-fold="plane"]')).not.toBeNull();
    expect(phaseEl("enrich").closest(".ds-tip")).toHaveTextContent("assigned by the hub");
    expect(document.querySelector("[data-phase-trigger]")).toHaveTextContent("@lingua");
  });

  it("keeps the strip's count in the header between phases and once the run completes", async () => {
    const run = running(null).pipeline_run;
    tasksReply({ active: null, closed: [], blocked: null, pipeline_run: { ...run, status: "between", phases: [run.phases[0], { slug: "enrich", state: "pending", seq: null }] } });
    render(<WorkgroupView workgroup={owned} profiles={crew} connectionId="local" />);
    await waitFor(() => expect(document.querySelector('[data-phase-trigger="idle"]')).not.toBeNull());
    expect(document.querySelector('[data-phase-trigger="idle"]')).toHaveTextContent("setup · between phases");
    expect(document.querySelector('[data-phase-trigger="idle"]')).toHaveTextContent("1 of 2");
  });

  it("puts a blocked phase and its reason in red on the header, with nothing rippling", async () => {
    const run = running(null).pipeline_run;
    tasksReply({ active: null, closed: [], blocked: { slug: "enrich", reason: "BLOCKED enrich · no source photos" }, pipeline_run: { ...run, status: "blocked" } });
    render(<WorkgroupView workgroup={owned} profiles={crew} connectionId="local" />);
    await waitFor(() => expect(document.querySelector('[data-phase-trigger="blocked"]')).not.toBeNull());
    const trigger = document.querySelector('[data-phase-trigger="blocked"]');
    expect(trigger).toHaveTextContent("blocked · no source photos");
    expect(trigger).toHaveTextContent("1 of 2");
    expect(trigger.querySelector('[data-fold="house"]')).not.toBeNull();
  });

  it("gives a phase its state as its ground, with no check and no state word, and never names the pipeline twice", async () => {
    tasksReply({
      active: null,
      closed: [],
      blocked: null,
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
    render(<WorkgroupView workgroup={owned} profiles={crew} connectionId="local" />);

    await waitFor(() => expect(phaseEl("enrich")).not.toBeNull());
    expect([phaseEl("setup"), phaseEl("enrich")].map((el) => el.textContent)).toEqual(["#setup", "#enrich"]);
    expect(phaseEl("setup")).toHaveAccessibleName(/completed/);
    expect(phaseEl("enrich")).toHaveAccessibleName(/blocked/);
    const label = screen.getByText("pipeline", { exact: true });
    expect(label).toHaveClass(styles.pipelineLabel);
    expect(label.nextElementSibling).toContainElement(phaseEl("setup"));
    expect(screen.queryByText(/^pipeline · /)).toBeNull();
    expect(screen.queryByText("setup", { exact: true })).toBeNull();
  });

  it("draws no owner object for a daemon without phase_map", async () => {
    tasksReply(running({ slug: "enrich", title: "go", opened_seq: 42 }));
    render(<WorkgroupView workgroup={workgroup} profiles={crew} connectionId="local" />);

    await waitFor(() => expect(phaseEl("enrich")).not.toBeNull());
    expect(phaseEl("enrich").querySelector("[data-fold]")).toBeNull();
    expect(document.querySelector("[data-phase-trigger]")).toHaveTextContent("1 of 2");
  });
});
