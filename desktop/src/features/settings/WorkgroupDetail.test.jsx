import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";

const hubDetail = vi.hoisted(() => ({ value: {} }));

vi.mock("../../hooks/useProfileDetail.js", () => ({
  useProfileDetail: () => ({ detail: hubDetail.value, loading: false }),
}));

vi.mock("../../hooks/useUsage.js", () => ({
  useWorkgroupUsageDaily: () => ({ days: [], loading: false }),
}));

import WorkgroupDetail, { _clearWorkgroupMembersCache } from "./WorkgroupDetail.jsx";

beforeEach(() => {
  hubDetail.value = {};
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

    const bar = screen.getByRole("progressbar", { name: "Fetching latest workgroup settings" });
    expect(bar.getAttribute("style")).toBeNull();
    expect(bar.outerHTML).not.toContain("#446");
  });

  it("lists its sections in the searchable settings rail", async () => {
    invoke.mockResolvedValue([]);
    render(
      <WorkgroupDetail
        workgroup={{ id: "wg-1", profile: "mira", hub_id: "mira", is_hub: true }}
        profiles={[{ name: "mira", pubkey_b64: "hub", accent: "#446" }]}
        connectionId="casa"
      />,
    );
    const rail = screen.getByRole("navigation", { name: "Settings sections" });
    const items = () => within(rail).getAllByRole("button").map((b) => b.textContent);
    await waitFor(() => expect(items()).toEqual(expect.arrayContaining(["Overview", "Budget", "Briefing", "Members", "Danger zone"])));
    fireEvent.change(within(rail).getByRole("searchbox", { name: "Search settings" }), { target: { value: "brief" } });
    await waitFor(() => expect(items()).toEqual(["Briefing"]), { timeout: 3000 });
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
  return screen.getByText(key, { selector: "span" }).closest("[data-settings-row]");
}

function pipelineSection() {
  return screen.getByRole("heading", { name: "Pipelines" }).closest("section");
}

describe("WorkgroupDetail — pipelines", () => {
  it("renders every declared chain read-only, keyed as written, with the trigger in words", async () => {
    mockHost();
    render(<WorkgroupDetail workgroup={PIPELINE_WG} profiles={PROFILES} connectionId="casa" />);

    await waitFor(() => expect(screen.getByRole("heading", { name: "Pipelines" })).toBeInTheDocument());
    expect(within(pipelineRow("setup")).getByText("#enrich")).toBeInTheDocument();
    expect(within(pipelineRow("media-update")).getByText("#media-qa")).toBeInTheDocument();
    expect(screen.getAllByText("starts at launch")).toHaveLength(1);
    expect(within(pipelineRow("setup")).getByText("starts at launch")).toBeInTheDocument();
    expect(within(pipelineRow("media-update")).getByText("on demand")).toBeInTheDocument();
  });

  it("marks every phase with its declared owner and the run's state, on the run's chain only", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "workgroup_members") return [];
      if (cmd === "workgroup_tasks") {
        return {
          pipeline_run: {
            pipeline: "setup",
            status: "blocked",
            cost: { usd: 0.42 },
            phases: [{ slug: "setup", state: "completed" }, { slug: "enrich", state: "current" }],
          },
        };
      }
      return null;
    });
    const profiles = [...PROFILES, { name: "pixel", pubkey_b64: "px", accent: "#2cb3b5", fold: "rocket" }];
    render(<WorkgroupDetail workgroup={PIPELINE_WG} profiles={profiles} connectionId="casa" />);

    await waitFor(() => expect(screen.getByText("last run blocked · 1 of 2 · $0.42")).toBeInTheDocument());
    const setupChip = within(pipelineRow("setup")).getByText("#setup").closest("[data-state]");
    expect(setupChip.dataset.state).toBe("completed");
    expect(setupChip.querySelector('[data-fold="rocket"]')).not.toBeNull();
    const enrichChip = within(pipelineRow("setup")).getByText("#enrich").closest("[data-state]");
    expect(enrichChip.dataset.state).toBe("blocked");
    expect(enrichChip.querySelector("[data-fold]")).toBeNull();
    const mediaChip = within(pipelineRow("media-update")).getByText("#media-update").closest("[data-state]");
    expect(mediaChip.dataset.state).toBe("pending");
    expect(within(pipelineRow("media-update")).queryByText(/last run/)).toBeNull();
  });

  it("draws an owner that is not a local profile as the grey unfolded object", async () => {
    mockHost();
    render(<WorkgroupDetail workgroup={PIPELINE_WG} profiles={PROFILES} connectionId="casa" />);

    await waitFor(() => expect(screen.getByRole("heading", { name: "Pipelines" })).toBeInTheDocument());
    const chip = within(pipelineRow("setup")).getByText("#setup").closest("[data-state]");
    expect(chip.querySelector("[data-unfolded]")).not.toBeNull();
  });

  it("offers no control at all inside the pipelines section", async () => {
    mockHost();
    render(<WorkgroupDetail workgroup={PIPELINE_WG} profiles={PROFILES} connectionId="casa" />);

    await waitFor(() => expect(screen.getByRole("heading", { name: "Pipelines" })).toBeInTheDocument());
    const section = within(pipelineSection());
    expect(section.queryAllByRole("button")).toHaveLength(0);
    expect(section.queryAllByRole("textbox")).toHaveLength(0);
    expect(pipelineSection().querySelectorAll("input, select")).toHaveLength(0);
  });

  it("only reads the run state for the pipelines section, never triggers one", async () => {
    mockHost();
    render(<WorkgroupDetail workgroup={PIPELINE_WG} profiles={PROFILES} connectionId="casa" />);

    await waitFor(() => expect(screen.getByRole("heading", { name: "Pipelines" })).toBeInTheDocument());
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("workgroup_tasks", { profile: "mira", wgId: "wg-1", connectionId: "casa" }));
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

    await waitFor(() => expect(screen.getByRole("heading", { name: "Pipelines" })).toBeInTheDocument());
    expect(
      screen.getByText("No launch pipeline. Nothing starts until a trigger."),
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

    await waitFor(() => expect(screen.getByRole("heading", { name: "Pipelines" })).toBeInTheDocument());
    expect(screen.getByText("No pipelines. This is a deliberation workgroup.")).toBeInTheDocument();
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

    await waitFor(() => expect(screen.getByRole("heading", { name: "Pipelines" })).toBeInTheDocument());
    expect(screen.getByText(/Retired pipeline shape/)).toBeInTheDocument();
    expect(screen.getByText(/relaunch it from its recipe/)).toBeInTheDocument();
    expect(screen.queryByText("No pipelines. This is a deliberation workgroup.")).toBeNull();
  });

  it("never sends a pipeline edit through workgroup_update", async () => {
    mockHost();
    render(<WorkgroupDetail workgroup={PIPELINE_WG} profiles={PROFILES} connectionId="casa" />);

    await waitFor(() => expect(screen.getByRole("heading", { name: "Pipelines" })).toBeInTheDocument());
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

    await waitFor(() => expect(screen.getByRole("heading", { name: "Pipelines" })).toBeInTheDocument());
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

    await waitFor(() => expect(screen.getByRole("heading", { name: "Pipelines" })).toBeInTheDocument());
    expect(
      screen.getByText("No launch pipeline. Nothing starts until a trigger."),
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

  it("names a failed members read and retries it instead of showing none", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "workgroup_members") throw new Error("read timeout");
      return null;
    });
    render(
      <WorkgroupDetail
        workgroup={{ id: "wg-1", profile: "mira", hub_id: "mira", is_hub: true }}
        profiles={[{ name: "mira", pubkey_b64: "hub", accent: "#446" }]}
        connectionId="casa"
      />,
    );
    await screen.findByRole("alert");
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't load members");
    invoke.mockImplementation(async (cmd) => (cmd === "workgroup_members" ? [] : null));
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  });
});


describe("WorkgroupDetail budget cap", () => {
  it("clears the lifetime cap through workgroup_update", async () => {
    invoke.mockResolvedValue([]);
    const onSaved = vi.fn();
    render(
      <WorkgroupDetail
        workgroup={{ id: "wg-1", profile: "mira", hub_id: "mira", is_hub: true, budget_usd: 10, spent_usd: 1 }}
        profiles={[{ name: "mira", pubkey_b64: "hub", accent: "#446" }]}
        connectionId="casa"
        onSaved={onSaved}
      />,
    );
    fireEvent.click(screen.getByText("Edit cap"));
    fireEvent.change(screen.getByPlaceholderText("empty = unlimited"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("workgroup_update", {
      profile: "mira", wgId: "wg-1", budgetUsd: null, clearBudget: true, connectionId: "casa",
    }));
  });
});

describe("WorkgroupDetail — members", () => {
  const PROFILES_WITH_MEMBERS = [
    { name: "mira", pubkey_b64: "hub", accent: "#6572e4", fold: "crown" },
    { name: "pixel", pubkey_b64: "px", accent: "#2cb3b5", fold: "rocket", bio: "Builds the site." },
  ];

  function mockMembers() {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "workgroup_members") {
        return [
          { pubkey: "hub", joined: true },
          { pubkey: "px", joined: true },
        ];
      }
      return null;
    });
  }

  function memberRow(name) {
    return screen.getByText(name, { selector: "span" }).closest(".col");
  }

  it("lists what each member owns, and says the hub routes every phase", async () => {
    mockMembers();
    render(<WorkgroupDetail workgroup={PIPELINE_WG} profiles={PROFILES_WITH_MEMBERS} connectionId="casa" />);

    await waitFor(() => expect(screen.getByText("Builds the site.")).toBeInTheDocument());
    expect(within(memberRow("pixel")).getByText("#setup")).toBeInTheDocument();
    expect(within(memberRow("mira")).getByText("hub")).toBeInTheDocument();
    expect(within(memberRow("mira")).getByText("#media-update")).toBeInTheDocument();
  });

  it("keeps Remove behind the row menu and a confirmation, and opens the profile from there", async () => {
    mockMembers();
    const onNavigate = vi.fn();
    render(
      <WorkgroupDetail
        workgroup={PIPELINE_WG}
        profiles={PROFILES_WITH_MEMBERS}
        connectionId="casa"
        onNavigate={onNavigate}
      />,
    );

    await waitFor(() => expect(screen.getByText("Builds the site.")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Remove from workgroup" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "More for @pixel" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Open @pixel" }));
    expect(onNavigate).toHaveBeenCalledWith({ kind: "profile", id: "pixel" });

    fireEvent.click(screen.getByRole("button", { name: "More for @pixel" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Remove from workgroup…" }));
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() =>
      expect(invoke).toHaveBeenCalledWith("workgroup_action", expect.objectContaining({ action: "kick", memberPubkey: "px" })),
    );
    fireEvent.click(screen.getByRole("button", { name: "More for @mira" }));
    expect(screen.getByRole("menuitem", { name: "Copy profile id" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Remove from workgroup…" })).toBeNull();
  });

  it("offers Remove only to the hub", async () => {
    mockMembers();
    render(<WorkgroupDetail workgroup={{ ...PIPELINE_WG, is_hub: false }} profiles={PROFILES_WITH_MEMBERS} connectionId="casa" />);
    await waitFor(() => expect(screen.getByText("Builds the site.")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "More for @pixel" }));
    expect(screen.getByRole("menuitem", { name: "Copy profile id" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Remove from workgroup…" })).toBeNull();
  });
});


describe("WorkgroupDetail — pipelines and members under search and older daemons", () => {
  it("lets the settings search hide the pipelines that do not match", async () => {
    invoke.mockImplementation(async (cmd) => (cmd === "workgroup_members" ? [] : null));
    render(<WorkgroupDetail workgroup={PIPELINE_WG} profiles={PROFILES} connectionId="casa" />);
    const rail = screen.getByRole("navigation", { name: "Settings sections" });
    const items = () => within(rail).getAllByRole("button").map((b) => b.textContent);
    await waitFor(() => expect(items()).toContain("Pipelines"), { timeout: 3000 });
    fireEvent.change(within(rail).getByRole("searchbox", { name: "Search settings" }), { target: { value: "brief" } });
    await waitFor(() => expect(items()).toEqual(["Briefing"]), { timeout: 3000 });
    fireEvent.change(within(rail).getByRole("searchbox", { name: "Search settings" }), { target: { value: "media-qa" } });
    await waitFor(() => expect(items()).toContain("Pipelines"), { timeout: 3000 });
    expect(pipelineRow("setup").hidden).toBe(true);
    expect(pipelineRow("media-update").hidden).toBe(false);
  });

  it("names a remote member by its peer alias, matches its phases by peer id, and shows no owns line without a phase_map", async () => {
    hubDetail.value = { peers: [{ id: "pixel", alias: "Builder (casa)", pubkey: "remote-px" }] };
    invoke.mockImplementation(async (cmd) => (cmd === "workgroup_members" ? [{ pubkey: "remote-px", joined: true, bio: "Remote builder." }] : null));
    const { unmount } = render(<WorkgroupDetail workgroup={PIPELINE_WG} profiles={PROFILES} connectionId="casa" />);
    await waitFor(() => expect(screen.getByText("Remote builder.")).toBeInTheDocument());
    const row = screen.getByText("Remote builder.").closest(".col");
    expect(within(row).getByText("#setup")).toBeInTheDocument();
    expect(within(row).getByRole("button", { name: "More for @Builder (casa)" })).toBeInTheDocument();
    unmount();
    _clearWorkgroupMembersCache();

    render(<WorkgroupDetail workgroup={{ ...PIPELINE_WG, phase_map: {} }} profiles={PROFILES} connectionId="casa" />);
    await waitFor(() => expect(screen.getByText("Remote builder.")).toBeInTheDocument());
    expect(screen.queryByText("owns")).toBeNull();
  });

  it("falls back to the peer id when the alias is empty", async () => {
    hubDetail.value = { peers: [{ id: "pixel", alias: "", pubkey: "remote-px" }] };
    invoke.mockImplementation(async (cmd) => (cmd === "workgroup_members" ? [{ pubkey: "remote-px", joined: true, bio: "Remote builder." }] : null));
    render(<WorkgroupDetail workgroup={PIPELINE_WG} profiles={PROFILES} connectionId="casa" />);
    await waitFor(() => expect(screen.getByText("Remote builder.")).toBeInTheDocument());
    const row = screen.getByText("Remote builder.").closest(".col");
    expect(within(row).getByRole("button", { name: "More for @pixel" })).toBeInTheDocument();
    expect(within(row).getByText("#setup")).toBeInTheDocument();
  });
});
