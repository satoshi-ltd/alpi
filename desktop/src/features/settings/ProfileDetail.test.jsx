import { render, screen } from "@testing-library/react";
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
  AccentField: () => null,
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
  VoiceField: () => null,
}));
vi.mock("./fields/alp.jsx", () => ({
  PeersField: () => null,
  TcpPortField: () => null,
  WorkgroupsField: () => null,
}));
vi.mock("./fields/services.jsx", () => ({
  EmailCell: () => null,
  SubsystemsCell: () => null,
}));
vi.mock("./fields/devices.jsx", () => ({ DevicesField: () => null }));
vi.mock("./fields/DaemonField.jsx", () => ({ DaemonField: () => null }));
vi.mock("./fields/network.jsx", () => ({
  HostPortField: () => null,
  NetworkAddressField: () => null,
  PairingNameField: () => null,
}));
vi.mock("./fields/maintenance.jsx", () => ({
  DeleteProfileAction: () => null,
  StorageField: () => null,
  _clearStorageCache: () => {},
}));

import ProfileDetail from "./ProfileDetail.jsx";

describe("ProfileDetail", () => {
  it("shows the settings sync progress bar under the header", () => {
    render(
      <ProfileDetail
        profile={{ name: "pulse", accent: "#10b981", budget: 2 }}
        profiles={[]}
        activeConnection={{ id: "remote" }}
        connectionSyncing
      />,
    );

    expect(screen.getByRole("progressbar", { name: "Fetching latest settings" })).toBeInTheDocument();
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
