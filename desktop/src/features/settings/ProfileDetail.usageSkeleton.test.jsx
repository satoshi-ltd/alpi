import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { usageState, detailState, snapshotState } = vi.hoisted(() => ({
  usageState: { days: [], loading: true, total30: null },
  detailState: { detail: {}, loading: false, refresh: () => {} },
  snapshotState: { snapshot: null, error: new Error("old"), refresh: () => {} },
}));
vi.mock("../../hooks/useProfileDetail.js", () => ({ useProfileDetail: () => detailState }));
vi.mock("../../hooks/useProfileSnapshot.js", () => ({ useProfileSnapshot: () => snapshotState }));
vi.mock("../../hooks/useUsage.js", () => ({ useUsageDaily: () => usageState }));
vi.mock("../../primitives/Notification.jsx", () => ({ useNotify: () => vi.fn() }));
vi.mock("./Usage.jsx", () => ({ default: () => <div data-testid="usage-content" /> }));
vi.mock("./fields/boundaries.jsx", () => ({ BudgetField: () => null, SandboxField: () => null, WorkspaceField: () => null }));
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
vi.mock("./fields/maintenance.jsx", () => ({ DeleteProfileAction: () => null, StorageField: () => null, _clearStorageCache: () => {} }));
vi.mock("./fields/PeersField.jsx", () => ({ PeersField: () => null }));
vi.mock("./fields/TcpPortField.jsx", () => ({ TcpPortField: () => null }));

import ProfileDetail from "./ProfileDetail.jsx";

const ui = () => (
  <ProfileDetail profile={{ name: "mira", accent: "#10b981" }} profiles={[]} activeConnection={{ id: "local" }} />
);
const bones = () => screen.queryByRole("img", { name: "Loading usage" });

beforeEach(() => {
  vi.useFakeTimers();
  usageState.days = [];
  usageState.loading = true;
});
afterEach(() => vi.useRealTimers());

describe("ProfileDetail usage skeleton wiring", () => {
  it("shows no bones before 150 ms, holds them 400 ms, then renders the content", () => {
    const view = render(ui());
    act(() => vi.advanceTimersByTime(149));
    expect(bones()).toBeNull();
    act(() => vi.advanceTimersByTime(1));
    expect(bones()).not.toBeNull();
    usageState.days = [{ day: "d" }];
    usageState.loading = false;
    view.rerender(ui());
    act(() => vi.advanceTimersByTime(399));
    expect(bones()).not.toBeNull();
    act(() => vi.advanceTimersByTime(1));
    expect(bones()).toBeNull();
    expect(screen.getByTestId("usage-content")).toBeInTheDocument();
  });

  it("keeps the Usage section mounted through the hold for a profile without usage", () => {
    const view = render(ui());
    act(() => vi.advanceTimersByTime(150));
    expect(bones()).not.toBeNull();
    act(() => vi.advanceTimersByTime(50));
    usageState.loading = false;
    view.rerender(ui());
    act(() => vi.advanceTimersByTime(349));
    expect(screen.getByText("last 14 days")).toBeInTheDocument();
    expect(bones()).not.toBeNull();
    act(() => vi.advanceTimersByTime(1));
    expect(bones()).toBeNull();
    expect(screen.queryByText("last 14 days")).toBeNull();
  });

  it("fades the content in only after bones were shown", () => {
    usageState.days = [{ day: "d" }];
    usageState.loading = false;
    const cached = render(ui());
    expect(screen.getByTestId("usage-content").parentElement.className).not.toMatch(/reveal/);
    cached.unmount();

    usageState.days = [];
    usageState.loading = true;
    const view = render(ui());
    act(() => vi.advanceTimersByTime(150));
    usageState.days = [{ day: "d" }];
    usageState.loading = false;
    view.rerender(ui());
    act(() => vi.advanceTimersByTime(400));
    expect(screen.getByTestId("usage-content").parentElement.className).toMatch(/reveal/);
  });
});
