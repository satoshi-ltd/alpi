import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { stableDetail, refreshProfileDetail } = vi.hoisted(() => ({
  stableDetail: {},
  refreshProfileDetail: vi.fn(),
}));

vi.mock("../../hooks/useProfileDetail.js", () => ({
  useProfileDetail: () => ({
    detail: stableDetail,
    loading: false,
    refresh: refreshProfileDetail,
  }),
}));

vi.mock("../../hooks/useUsage.js", () => ({
  useUsageDaily: () => ({ days: [], loading: false }),
}));

vi.mock("../../primitives/Notification.jsx", () => ({
  useNotify: () => vi.fn(),
}));

vi.mock("./Usage.jsx", () => ({ default: () => null }));
vi.mock("./fields/boundaries.jsx", () => ({
  BudgetField: () => null,
  SandboxField: () => null,
  WorkspaceField: () => null,
}));
vi.mock("./fields/agent.jsx", () => ({
  AddProviderField: () => null,
  McpField: () => null,
  ModelField: () => null,
  ReasoningEffortField: () => null,
  TierField: () => null,
  VisionModelField: () => <span>vision field</span>,
  VoiceField: () => null,
}));
const workgroupsProbe = vi.hoisted(() => ({ count: 0 }));
vi.mock("./fields/alp.jsx", async () => {
  const { useEffect } = await import("react");
  return {
    PeersField: () => null,
    PipelineLimitField: () => <span>pipeline limit</span>,
    TcpPortField: () => null,
    WorkgroupsField: ({ onCountChange }) => {
      const count = workgroupsProbe.count;
      useEffect(() => { onCountChange?.(count); }, [count, onCountChange]);
      return <span>workgroups probe</span>;
    },
  };
});
vi.mock("./fields/services.jsx", () => ({
  EmailCell: () => null,
}));
vi.mock("./fields/devices.jsx", () => ({ DevicesField: () => null }));
vi.mock("./fields/DaemonField.jsx", () => ({
  DaemonField: ({ connectionId, selfUpdate }) => (
    <span data-testid="daemon-connection" data-self-update={String(selfUpdate)}>{connectionId}</span>
  ),
}));
vi.mock("./fields/network.jsx", () => ({
  NetworkAddressField: () => <span>client address</span>,
  PairingNameField: () => <span>client name</span>,
  PrivateRouteField: () => <span>private route</span>,
  PublicRouteField: () => <span>public route</span>,
}));
vi.mock("./fields/maintenance.jsx", () => ({
  DeleteProfileAction: () => null,
  StorageField: () => null,
  _clearStorageCache: () => {},
}));

import ProfileDetail from "./ProfileDetail.jsx";

describe("ProfileDetail", () => {
  it("matches the chat header model and budget treatment", () => {
    const { container } = render(
      <ProfileDetail
        profile={{
          name: "pulse",
          accent: "#10b981",
          model: "openrouter/deepseek/deepseek-v4-flash-latest",
          budget_daily_usd: 10,
          budget_used_usd: 0.26,
        }}
        profiles={[]}
        activeConnection={{ id: "remote" }}
      />,
    );

    const model = screen.getByText("deepseek-v4-flash-latest");
    expect(model.closest(".ds-tip-escape")).toBeInTheDocument();
    fireEvent.mouseEnter(model.closest(".ds-tip-escape"));
    expect(screen.getByText("openrouter/deepseek/deepseek-v4-flash-latest"))
      .toHaveClass("ds-tip-wide");
    expect(container.querySelector(".ds-meter")).toHaveTextContent("$0.26/$10.00");
    const budgetTip = container.querySelector(".ds-meter").closest(".ds-tip-escape");
    expect(budgetTip).toBeInTheDocument();
    fireEvent.mouseEnter(budgetTip);
    expect(screen.getByText("Daily budget")).toBeInTheDocument();
    expect(container.querySelector(".ds-meter [role='progressbar']"))
      .toHaveAttribute("aria-valuenow", "3");
  });

  it("shows the settings sync progress bar under the header", () => {
    render(
      <ProfileDetail
        profile={{ name: "pulse", accent: "#10b981", budget: 2 }}
        profiles={[]}
        activeConnection={{ id: "remote" }}
        connectionSyncing
      />,
    );

    const bar = screen.getByRole("progressbar", { name: "Fetching latest settings" });
    expect(bar.getAttribute("style")).toBeNull();
    expect(bar.outerHTML).not.toContain("#10b981");
  });

  it("keeps daemon and client access in one Service section", () => {
    const view = render(
      <ProfileDetail
        profile={{ name: "default" }}
        profiles={[]}
        activeConnection={{ id: "local", kind: "local" }}
      />,
    );

    expect(screen.getAllByRole("heading", { name: "Service" })).toHaveLength(1);
    expect(screen.queryByText("Client access")).toBeNull();
    expect(screen.getByText("client address")).toBeInTheDocument();
    expect(screen.getByText("client name")).toBeInTheDocument();
    expect(screen.getByText("private route")).toBeInTheDocument();
    expect(screen.getByText("public route")).toBeInTheDocument();
    expect(screen.getByTestId("daemon-connection")).toHaveTextContent("local");

    view.rerender(
      <ProfileDetail
        profile={{ name: "default" }}
        profiles={[]}
        activeConnection={{ id: "remote", kind: "remote", role: "admin" }}
      />,
    );
    expect(screen.queryByText("private route")).toBeNull();
    expect(screen.getByTestId("daemon-connection")).toHaveTextContent("remote");
  });
});

describe("ProfileDetail — daemon update", () => {
  it.each([
    [{ self_update: false }, "false"],
    [{ self_update: true }, "true"],
    [{}, "true"],
  ])("passes %j to the daemon field as selfUpdate=%s", (flags, expected) => {
    render(
      <ProfileDetail
        profile={{ name: "default" }}
        profiles={[]}
        activeConnection={{ id: "remote", kind: "remote", role: "admin", ...flags }}
      />,
    );

    expect(screen.getByTestId("daemon-connection")).toHaveAttribute("data-self-update", expected);
  });
});

describe("ProfileDetail — routing tiers gating", () => {
  it("shows tier rows only when the daemon reports tiers in profile.detail", () => {
    Object.assign(stableDetail, {
      models: ["openrouter/main"],
      tiers: {
        fast: { model: "", effort: "", reasoning_supported: false },
        deep: { model: "", effort: "", reasoning_supported: false },
      },
    });
    const first = render(
      <ProfileDetail
        profile={{ name: "pulse" }}
        profiles={[]}
        activeConnection={{ id: "remote" }}
      />,
    );
    expect(screen.getByText("providers")).toBeInTheDocument();
    expect(screen.getByText("fast model")).toBeInTheDocument();
    expect(screen.getByText("deep model")).toBeInTheDocument();
    first.unmount();

    // Old daemon: detail has models but no tiers key — rows must not render.
    delete stableDetail.tiers;
    render(
      <ProfileDetail
        profile={{ name: "pulse" }}
        profiles={[]}
        activeConnection={{ id: "remote" }}
      />,
    );
    expect(screen.queryByText("fast model")).toBeNull();
    delete stableDetail.models;
  });
});

describe("ProfileDetail — vision model gating", () => {
  it("shows the row only when the daemon reports the read_image setting", () => {
    Object.assign(stableDetail, { models: ["openrouter/main"], vision_model: "" });
    const first = render(
      <ProfileDetail
        profile={{ name: "pulse" }}
        profiles={[]}
        activeConnection={{ id: "remote" }}
      />,
    );
    expect(screen.getByText("vision model")).toBeInTheDocument();
    expect(screen.getByText("vision field")).toBeInTheDocument();
    first.unmount();

    delete stableDetail.vision_model;
    render(
      <ProfileDetail
        profile={{ name: "pulse" }}
        profiles={[]}
        activeConnection={{ id: "remote" }}
      />,
    );
    expect(screen.queryByText("vision model")).toBeNull();
    delete stableDetail.models;
  });

  it("keeps a configured override clearable after its provider disappears", () => {
    Object.assign(stableDetail, {
      models: [],
      vision_model: "openrouter/deepseek/deepseek-v4-flash-vision-exp",
    });
    render(
      <ProfileDetail
        profile={{ name: "pulse" }}
        profiles={[]}
        activeConnection={{ id: "remote" }}
      />,
    );
    expect(screen.getByText("vision model")).toBeInTheDocument();
    expect(screen.getByText("vision field")).toBeInTheDocument();
    delete stableDetail.models;
    delete stableDetail.vision_model;
  });
});


describe("ProfileDetail — workgroups row", () => {
  it("stays mounted while hidden so the loader can report a late count", () => {
    workgroupsProbe.count = 0;
    const { rerender } = render(
      <ProfileDetail profile={{ name: "mira", accent: "#10b981" }} profiles={[]} activeConnection={{ id: "local" }} />,
    );
    expect(screen.getByText("workgroups probe")).not.toBeVisible();
    expect(screen.getByText("workgroups")).not.toBeVisible();

    workgroupsProbe.count = 3;
    rerender(
      <ProfileDetail profile={{ name: "mira", accent: "#10b981" }} profiles={[]} activeConnection={{ id: "local" }} refreshTick={1} />,
    );
    expect(screen.getByText("workgroups probe")).toBeVisible();
    expect(screen.getByText("workgroups")).toBeInTheDocument();
  });
});


describe("ProfileDetail — concurrency gating", () => {
  it("hides the concurrency row when the daemon does not report the cap", () => {
    render(<ProfileDetail profile={{ name: "mira", accent: "#10b981" }} profiles={[]} activeConnection={{ id: "local" }} />);
    expect(screen.queryByText("concurrency")).toBeNull();
    expect(screen.queryByText("pipeline limit")).toBeNull();
  });

  it("shows it once the daemon exposes max_active_workgroups", () => {
    render(
      <ProfileDetail
        profile={{ name: "mira", accent: "#10b981", max_active_workgroups: 5, max_active_workgroups_origin: "default" }}
        profiles={[]}
        activeConnection={{ id: "local" }}
      />,
    );
    expect(screen.getByText("concurrency")).toBeInTheDocument();
    expect(screen.getByText("pipeline limit")).toBeInTheDocument();
  });
});

describe("ProfileDetail unsaved state", () => {
  it("writes a pending edit to the connection it was made on, even after the view moved to another daemon", async () => {
    const { invoke } = await import("@tauri-apps/api/core");
    const { waitFor } = await import("@testing-library/react");
    invoke.mockImplementation(async (cmd) => (cmd === "draft_identity" ? "drafted bio" : null));
    const profile = { name: "doc", model: "a/b" };
    const view = render(<ProfileDetail profile={profile} profiles={[]} activeConnection={{ id: "local", kind: "local" }} />);
    fireEvent.change(screen.getByPlaceholderText("public identity — visible to peers"), { target: { value: "typed" } });
    fireEvent.click(screen.getByRole("button", { name: "Draft" }));
    await waitFor(() => expect(screen.getByPlaceholderText("public identity — visible to peers").value).toBe("drafted bio"));
    view.rerender(<ProfileDetail profile={profile} profiles={[]} activeConnection={{ id: "remote", kind: "remote", role: "admin" }} />);
    view.unmount();
    const writes = invoke.mock.calls.filter(([cmd]) => cmd === "set_config_field");
    expect(writes).toHaveLength(1);
    expect(writes[0][1]).toMatchObject({ profile: "doc", value: "drafted bio", connectionId: "local" });
    invoke.mockReset();
  });

  it("reports an unsaved identity draft and saves a pending debounced field on unmount", async () => {
    const { invoke } = await import("@tauri-apps/api/core");
    const { hasDirtySettings } = await import("../../lib/settingsDirty.js");
    const { waitFor } = await import("@testing-library/react");
    invoke.mockImplementation(async (cmd) => (cmd === "draft_identity" ? "drafted bio" : null));
    const view = render(
      <ProfileDetail profile={{ name: "doc", model: "a/b" }} profiles={[]} activeConnection={{ id: "local", kind: "local" }} />,
    );
    expect(hasDirtySettings()).toBe(false);
    fireEvent.change(screen.getByPlaceholderText("public identity — visible to peers"), { target: { value: "typed" } });
    expect(hasDirtySettings()).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Draft" }));
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("draft_identity", { profile: "doc" }));
    await waitFor(() => expect(screen.getByPlaceholderText("public identity — visible to peers").value).toBe("drafted bio"));
    expect(invoke).not.toHaveBeenCalledWith("set_config_field", expect.anything());
    view.unmount();
    expect(invoke).toHaveBeenCalledWith("set_config_field", expect.objectContaining({ profile: "doc", value: "drafted bio", connectionId: "local" }));
    expect(hasDirtySettings()).toBe(false);
    invoke.mockReset();
  });
});

describe("ProfileDetail appearance", () => {
  const profile = { name: "doc", model: "a/b", accent: "#3899e2", fold: "shield" };
  const mount = () =>
    render(<ProfileDetail profile={profile} profiles={[]} activeConnection={{ id: "local", kind: "local" }} />);

  it("shows the profile's current object and colour", async () => {
    const { invoke } = await import("@tauri-apps/api/core");
    invoke.mockImplementation(async () => null);
    mount();
    expect(screen.getByText("appearance")).toBeInTheDocument();
    expect(screen.queryByText("accent")).toBeNull();
    expect(screen.getByRole("button", { name: "blue shield" })).toBeInTheDocument();
    invoke.mockReset();
  });

  it("shows the default profile's alpaca as read-only text, with no picker", async () => {
    const { invoke } = await import("@tauri-apps/api/core");
    invoke.mockImplementation(async () => null);
    const { container } = render(
      <ProfileDetail profile={{ name: "default", fold: "alpaca", accent: null }} profiles={[]} activeConnection={{ id: "local", kind: "local" }} />,
    );
    expect(screen.getByText("alpaca · brand accent")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /alpaca|diamond/ })).toBeNull();
    expect([...container.querySelectorAll("[data-fold='alpaca']")].length).toBeGreaterThan(0);
    invoke.mockReset();
  });

  it("falls back to the diamond when the daemon reports no fold", async () => {
    const { invoke } = await import("@tauri-apps/api/core");
    invoke.mockImplementation(async () => null);
    render(<ProfileDetail profile={{ name: "doc", accent: "#3899e2" }} profiles={[]} activeConnection={{ id: "local", kind: "local" }} />);
    expect(screen.getByRole("button", { name: "blue diamond" })).toBeInTheDocument();
    invoke.mockReset();
  });

  it("saves a picked object to tui.fold and leaves the accent unwritten", async () => {
    const { invoke } = await import("@tauri-apps/api/core");
    const { waitFor } = await import("@testing-library/react");
    invoke.mockImplementation(async () => null);
    mount();
    fireEvent.click(screen.getByRole("button", { name: "blue shield" }));
    fireEvent.click(screen.getByRole("button", { name: "heart" }));
    expect(screen.getByRole("button", { name: "blue heart" })).toBeInTheDocument();
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("set_config_field", { profile: "doc", key: "tui.fold", value: "heart", connectionId: "local" }));
    expect(invoke).not.toHaveBeenCalledWith("set_config_field", expect.objectContaining({ key: "tui.accent" }));
    invoke.mockReset();
  });

  it("saves a picked colour to tui.accent and leaves the fold unwritten", async () => {
    const { invoke } = await import("@tauri-apps/api/core");
    const { waitFor } = await import("@testing-library/react");
    invoke.mockImplementation(async () => null);
    mount();
    fireEvent.click(screen.getByRole("button", { name: "blue shield" }));
    fireEvent.click(screen.getByRole("button", { name: "rose #f36a8a" }));
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("set_config_field", { profile: "doc", key: "tui.accent", value: "#f36a8a", connectionId: "local" }));
    expect(invoke).not.toHaveBeenCalledWith("set_config_field", expect.objectContaining({ key: "tui.fold" }));
    invoke.mockReset();
  });

  it("saves the reset as the diamond", async () => {
    const { invoke } = await import("@tauri-apps/api/core");
    const { waitFor } = await import("@testing-library/react");
    invoke.mockImplementation(async () => null);
    mount();
    fireEvent.click(screen.getByRole("button", { name: "blue shield" }));
    fireEvent.click(screen.getByRole("button", { name: "Reset to diamond" }));
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("set_config_field", { profile: "doc", key: "tui.fold", value: "diamond", connectionId: "local" }));
    invoke.mockReset();
  });
});
