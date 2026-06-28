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
  VoiceField: () => null,
}));
vi.mock("./fields/alp.jsx", () => ({
  PeersField: () => null,
  TcpPortField: () => null,
  WorkgroupsField: () => null,
}));
vi.mock("./fields/services.jsx", () => ({
  EmailCell: () => null,
  SchedulesSection: () => null,
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
