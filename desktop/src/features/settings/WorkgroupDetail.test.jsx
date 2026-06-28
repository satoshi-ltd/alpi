import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";

vi.mock("../../hooks/useProfileDetail.js", () => ({
  useProfileDetail: () => ({ detail: {}, loading: false }),
}));

vi.mock("../../hooks/useUsage.js", () => ({
  useWorkgroupUsageDaily: () => ({ days: [], loading: false }),
}));

vi.mock("../../primitives/Notification.jsx", () => ({
  useNotify: () => vi.fn(),
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
