import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
