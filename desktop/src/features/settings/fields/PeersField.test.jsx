import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, screen, cleanup, waitFor } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";

import { PeersField } from "./PeersField.jsx";

vi.mock("../../../primitives/Notification.jsx", async () => ({
  useNotify: () => () => {},
}));

describe("PeersField — onRefresh wiring", () => {
  beforeEach(() => {
    invoke.mockReset();
  });
  afterEach(() => cleanup());

  it("calls onRefresh after a successful discard", async () => {
    const onRefresh = vi.fn(async () => {});
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "peers_pending_list") {
        return [{ pubkey: "X+iAJ", first_seen: 1, last_seen: 2 }];
      }
      if (cmd === "probe_peers") return [];
      if (cmd === "peers_pending_discard") return null;
      return null;
    });

    render(
      <PeersField
        profile={{ name: "mirai", peers: [] }}
        profiles={[]}
        onRefresh={onRefresh}
      />,
    );

    fireEvent.click(await screen.findByText(/pending invite/i));
    fireEvent.click(await screen.findByText("Discard"));

    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith(
        "peers_pending_discard",
        { profile: "mirai", pubkey: "X+iAJ" },
      );
      expect(onRefresh).toHaveBeenCalled();
    });
  });
});
