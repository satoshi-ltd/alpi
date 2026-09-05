import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { invoke, detailState, snapshotState } = vi.hoisted(() => ({
  invoke: vi.fn(),
  detailState: { detail: {}, loading: false, refresh: () => {} },
  snapshotState: { snapshot: null, error: new Error("old daemon"), refresh: () => {} },
}));
vi.mock("@tauri-apps/api/core", () => ({ invoke }));
vi.mock("../../hooks/useProfileDetail.js", () => ({ useProfileDetail: () => detailState }));
vi.mock("../../hooks/useProfileSnapshot.js", () => ({ useProfileSnapshot: () => snapshotState }));
vi.mock("../../hooks/useUsage.js", () => ({ useUsageDaily: () => ({ days: [], loading: false }) }));
vi.mock("../../primitives/Notification.jsx", () => ({ useNotify: () => vi.fn() }));
vi.mock("./Usage.jsx", () => ({ default: () => null }));
vi.mock("./fields/boundaries.jsx", () => ({
  AccentField: () => null, BudgetField: () => null, SandboxField: () => null, WorkspaceField: () => null,
}));
vi.mock("./fields/agent.jsx", () => ({
  AddProviderField: () => null, McpField: () => null, ModelField: () => null, ReasoningEffortField: () => null,
  TierField: () => null, VisionModelField: () => null, VoiceField: () => null,
}));
vi.mock("./fields/services.jsx", () => ({ EmailCell: () => null }));
vi.mock("./fields/devices.jsx", () => ({ DevicesField: () => null }));
vi.mock("./fields/DaemonField.jsx", () => ({ DaemonField: () => null }));
vi.mock("./fields/network.jsx", () => ({
  NetworkAddressField: () => null, PairingNameField: () => null, PrivateRouteField: () => null, PublicRouteField: () => null,
}));
vi.mock("./fields/maintenance.jsx", () => ({
  DeleteProfileAction: () => null, StorageField: () => null, _clearStorageCache: () => {},
}));
vi.mock("./fields/PeersField.jsx", () => ({ PeersField: () => null }));
vi.mock("./fields/TcpPortField.jsx", () => ({ TcpPortField: () => null }));

import ProfileDetail from "./ProfileDetail.jsx";

describe("ProfileDetail — workgroups row with the real loader", () => {
  it("fetches once and stays hidden when the daemon returns no workgroups", async () => {
    invoke.mockImplementation((cmd) => Promise.resolve(cmd === "workgroups" ? [] : {}));
    render(<ProfileDetail profile={{ name: "mira", accent: "#10b981" }} profiles={[]} activeConnection={{ id: "local" }} />);

    await waitFor(() => expect(invoke).toHaveBeenCalledWith("workgroups", expect.objectContaining({ profile: "mira" })));
    await new Promise((resolve) => setTimeout(resolve, 60));

    expect(invoke.mock.calls.filter(([cmd]) => cmd === "workgroups")).toHaveLength(1);
    expect(screen.queryByText("workgroups")).not.toBeVisible();
  });
});
