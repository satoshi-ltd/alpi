import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";

const { notifyMock } = vi.hoisted(() => ({ notifyMock: vi.fn() }));

vi.mock("../primitives/Notification.jsx", () => ({
  useNotify: () => notifyMock,
}));

vi.mock("../hooks/useProfileDetail.js", () => ({
  useProfileDetail: () => ({
    detail: {
      peers: [
        { id: "peer-1", name: "Muse", pubkey_b64: "pub-1" },
      ],
    },
  }),
}));

import CreateWorkgroupModal from "./CreateWorkgroupModal.jsx";

beforeEach(() => {
  invoke.mockReset();
  notifyMock.mockReset();
});

describe("CreateWorkgroupModal", () => {
  it("creates the workgroup on the selected connection", async () => {
    invoke.mockResolvedValueOnce("wg-1");
    render(
      <CreateWorkgroupModal
        open
        profiles={[{ name: "mira", counts: { peers: 1 } }]}
        connectionId="casa"
      />,
    );

    fireEvent.change(screen.getByPlaceholderText("team-alpha · roadmap · customers"), {
      target: { value: "Launch" },
    });
    fireEvent.click(screen.getByText("@peer-1"));
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("workgroup_create", {
        profile: "mira",
        name: "Launch",
        memberPeerIds: ["peer-1"],
        budgetUsd: null,
        briefing: null,
        pipeline: null,
        connectionId: "casa",
      });
    });
  });
});
