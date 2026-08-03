import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";

vi.mock("../../hooks/useProfileDetail.js", () => ({
  useProfileDetail: () => ({ detail: {}, loading: false }),
}));

vi.mock("../../hooks/useUsage.js", () => ({
  useWorkgroupUsageDaily: () => ({ days: [], loading: false }),
}));

import WorkgroupDetail, { _clearWorkgroupMembersCache } from "./WorkgroupDetail.jsx";

beforeEach(() => {
  _clearWorkgroupMembersCache();
  invoke.mockReset();
});

describe("WorkgroupDetail", () => {
  it("shows the settings sync progress bar under the header", () => {
    render(
      <WorkgroupDetail
        workgroup={{ id: "wg-1", profile: "mira", hub_id: "mira", is_hub: true }}
        profiles={[{ name: "mira", pubkey_b64: "hub", accent: "#446" }]}
        connectionId="casa"
        connectionSyncing
      />,
    );

    expect(screen.getByRole("progressbar", { name: "Fetching latest workgroup settings" })).toBeInTheDocument();
  });

  it("routes member reads to the selected connection", async () => {
    invoke.mockResolvedValueOnce([]);
    render(
      <WorkgroupDetail
        workgroup={{ id: "wg-1", profile: "mira", hub_id: "mira", is_hub: true }}
        profiles={[{ name: "mira", pubkey_b64: "hub", accent: "#446" }]}
        connectionId="casa"
      />,
    );
    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("workgroup_members", {
        profile: "mira",
        wgId: "wg-1",
        connectionId: "casa",
      });
    });
  });
});

const PIPELINE_WG = {
  id: "wg-1",
  name: "hotel",
  profile: "mira",
  hub_id: "mira",
  is_hub: true,
  pipelines: {
    setup: ["setup", "enrich"],
    "media-update": ["media-update", "media-qa"],
  },
  launch_pipeline: "setup",
  pipeline_mode: true,
  phase_map: {
    setup: { owner: "pixel", task: "Wire the skeleton" },
    "media-update": { owner: "mira", task: "Swap in the new photo set" },
  },
};

const PROFILES = [{ name: "mira", pubkey_b64: "hub", accent: "#446" }];

function mockHost() {
  invoke.mockImplementation(async (cmd) => {
    if (cmd === "workgroup_members") return [];
    return null;
  });
}

function pipelineRow(key) {
  return screen.getByText(key).closest("div.row");
}

function pipelineSection() {
  return screen.getByText("Pipelines").closest("section");
}

describe("WorkgroupDetail — pipelines", () => {
  it("renders every declared chain read-only with exactly one launch marker", async () => {
    mockHost();
    render(<WorkgroupDetail workgroup={PIPELINE_WG} profiles={PROFILES} connectionId="casa" />);

    await waitFor(() => expect(screen.getByText("Pipelines")).toBeInTheDocument());
    expect(within(pipelineRow("setup")).getByText("#enrich")).toBeInTheDocument();
    expect(within(pipelineRow("media-update")).getByText("#media-qa")).toBeInTheDocument();
    expect(screen.getAllByText("launch")).toHaveLength(1);
    expect(within(pipelineRow("setup")).getAllByText("launch")).toHaveLength(1);
  });

  it("offers no control at all inside the pipelines section", async () => {
    mockHost();
    render(<WorkgroupDetail workgroup={PIPELINE_WG} profiles={PROFILES} connectionId="casa" />);

    await waitFor(() => expect(screen.getByText("Pipelines")).toBeInTheDocument());
    const section = within(pipelineSection());
    expect(section.queryAllByRole("button")).toHaveLength(0);
    expect(section.queryAllByRole("textbox")).toHaveLength(0);
    expect(pipelineSection().querySelectorAll("input, select")).toHaveLength(0);
  });

  it("never reads the workgroup run state for the pipelines section", async () => {
    mockHost();
    render(<WorkgroupDetail workgroup={PIPELINE_WG} profiles={PROFILES} connectionId="casa" />);

    await waitFor(() => expect(screen.getByText("Pipelines")).toBeInTheDocument());
    expect(invoke).not.toHaveBeenCalledWith("workgroup_tasks", expect.anything());
    expect(invoke).not.toHaveBeenCalledWith("workgroup_trigger", expect.anything());
  });

  it("a launchless workgroup says nothing starts on its own", async () => {
    mockHost();
    render(
      <WorkgroupDetail
        workgroup={{ ...PIPELINE_WG, launch_pipeline: null }}
        profiles={PROFILES}
        connectionId="casa"
      />,
    );

    await waitFor(() => expect(screen.getByText("Pipelines")).toBeInTheDocument());
    expect(
      screen.getByText("nothing starts on its own — every chain awaits a trigger"),
    ).toBeInTheDocument();
    expect(screen.queryByText("launch")).toBeNull();
  });

  it("a deliberation workgroup shows no chains at all", async () => {
    mockHost();
    render(
      <WorkgroupDetail
        workgroup={{ ...PIPELINE_WG, pipelines: {}, launch_pipeline: null, phase_map: {} }}
        profiles={PROFILES}
        connectionId="casa"
      />,
    );

    await waitFor(() => expect(screen.getByText("Pipelines")).toBeInTheDocument());
    expect(screen.getByText("no pipeline (deliberation workgroup)")).toBeInTheDocument();
  });

  it("a retired-shape workgroup says it needs a relaunch, not that it deliberates", async () => {
    mockHost();
    render(
      <WorkgroupDetail
        workgroup={{
          ...PIPELINE_WG,
          pipelines: {},
          launch_pipeline: null,
          phase_map: {},
          needs_relaunch: true,
        }}
        profiles={PROFILES}
        connectionId="casa"
      />,
    );

    await waitFor(() => expect(screen.getByText("Pipelines")).toBeInTheDocument());
    expect(screen.getByText(/retired pipeline shape/)).toBeInTheDocument();
    expect(screen.getByText(/relaunch it from its recipe/)).toBeInTheDocument();
    expect(screen.queryByText("no pipeline (deliberation workgroup)")).toBeNull();
  });

  it("never sends a pipeline edit through workgroup_update", async () => {
    mockHost();
    render(<WorkgroupDetail workgroup={PIPELINE_WG} profiles={PROFILES} connectionId="casa" />);

    await waitFor(() => expect(screen.getByText("Pipelines")).toBeInTheDocument());
    fireEvent.change(screen.getAllByRole("textbox")[0], { target: { value: "new brief" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(invoke).toHaveBeenCalledWith("workgroup_update", {
        profile: "mira",
        wgId: "wg-1",
        briefing: "new brief",
        connectionId: "casa",
      }),
    );
  });

  it("a subscriber sees the same read-only chains and is never told to start one", async () => {
    mockHost();
    render(
      <WorkgroupDetail
        workgroup={{ ...PIPELINE_WG, is_hub: false }}
        profiles={PROFILES}
        connectionId="casa"
      />,
    );

    await waitFor(() => expect(screen.getByText("Pipelines")).toBeInTheDocument());
    expect(within(pipelineRow("media-update")).getByText("#media-qa")).toBeInTheDocument();
    expect(within(pipelineSection()).queryAllByRole("button")).toHaveLength(0);
  });

  it("a subscriber without a launch chain sees the same idle note as the hub", async () => {
    mockHost();
    render(
      <WorkgroupDetail
        workgroup={{ ...PIPELINE_WG, is_hub: false, launch_pipeline: null }}
        profiles={PROFILES}
        connectionId="casa"
      />,
    );

    await waitFor(() => expect(screen.getByText("Pipelines")).toBeInTheDocument());
    expect(
      screen.getByText("nothing starts on its own — every chain awaits a trigger"),
    ).toBeInTheDocument();
  });
});

describe("WorkgroupDetail — delete / leave", () => {
  it("hub delete: typed confirm removes the workgroup and navigates away", async () => {
    invoke.mockResolvedValue([]);
    const onSaved = vi.fn();
    const onGone = vi.fn();
    render(
      <WorkgroupDetail
        workgroup={{ id: "wg-1", name: "research", profile: "mira", hub_id: "mira", is_hub: true }}
        profiles={[{ name: "mira", pubkey_b64: "hub", accent: "#446" }]}
        connectionId="casa"
        onSaved={onSaved}
        onGone={onGone}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Delete workgroup…" }));
    fireEvent.change(screen.getAllByRole("textbox").at(-1), { target: { value: "research" } });
    fireEvent.click(screen.getByRole("button", { name: "Delete workgroup" }));

    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("workgroup_action", {
        profile: "mira", wgId: "wg-1", action: "remove",
        memberPubkey: null, connectionId: "casa",
      });
    });
    await waitFor(() => expect(onGone).toHaveBeenCalled());
    expect(onSaved).toHaveBeenCalled();
  });

  it("hub delete stays disarmed until the exact name is typed", async () => {
    invoke.mockResolvedValue([]);
    render(
      <WorkgroupDetail
        workgroup={{ id: "wg-1", name: "research", profile: "mira", hub_id: "mira", is_hub: true }}
        profiles={[{ name: "mira", pubkey_b64: "hub", accent: "#446" }]}
        connectionId="casa"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Delete workgroup…" }));
    fireEvent.change(screen.getAllByRole("textbox").at(-1), { target: { value: "wrong" } });
    expect(screen.getByRole("button", { name: "Delete workgroup" })).toBeDisabled();
  });

  it("member leave confirms and navigates away", async () => {
    invoke.mockResolvedValue([]);
    const onGone = vi.fn();
    render(
      <WorkgroupDetail
        workgroup={{ id: "wg-1", name: "research", profile: "mira", hub_id: "hub-x", is_hub: false }}
        profiles={[{ name: "mira", pubkey_b64: "member", accent: "#446" }]}
        connectionId="casa"
        onGone={onGone}
      />,
    );

    const [trigger] = screen.getAllByRole("button", { name: "Leave" });
    fireEvent.click(trigger);
    const buttons = screen.getAllByRole("button", { name: "Leave" });
    fireEvent.click(buttons[buttons.length - 1]);

    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("workgroup_action", {
        profile: "mira", wgId: "wg-1", action: "leave",
        memberPubkey: null, connectionId: "casa",
      });
    });
    await waitFor(() => expect(onGone).toHaveBeenCalled());
  });
});
