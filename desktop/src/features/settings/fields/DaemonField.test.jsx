import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { invoke, notify } = vi.hoisted(() => ({
  invoke: vi.fn(),
  notify: vi.fn(),
}));

vi.mock("@tauri-apps/api/core", () => ({ invoke }));
vi.mock("../../../primitives/Notification.jsx", () => ({
  useNotify: () => notify,
}));

import { DaemonField } from "./DaemonField.jsx";

describe("DaemonField", () => {
  beforeEach(() => {
    invoke.mockReset();
    notify.mockReset();
  });

  it("pins update to the connection rendered in Settings", async () => {
    invoke.mockResolvedValue({ updated: false, reason: "up-to-date", current: "0.14.9" });
    render(<DaemonField connectionId="remote-a" />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Update alpi" }));
    });

    expect(invoke).toHaveBeenCalledWith("daemon_update", { connectionId: "remote-a" });
  });

  it("pins restart to the same connection", async () => {
    invoke.mockResolvedValue({ ok: true });
    render(<DaemonField connectionId="remote-b" />);

    fireEvent.click(screen.getByRole("button", { name: "Restart daemon" }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "restart" } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Restart" }));
    });

    expect(invoke).toHaveBeenCalledWith("daemon_restart", { connectionId: "remote-b" });
  });

  it("explains both supported manual update paths", async () => {
    invoke.mockResolvedValue({ updated: false, reason: "manual" });
    render(<DaemonField connectionId="local" />);

    fireEvent.click(screen.getByRole("button", { name: "Update alpi" }));

    await waitFor(() => expect(notify).toHaveBeenCalledWith(expect.objectContaining({
      message: expect.stringContaining("docker compose pull"),
    })));
    expect(notify.mock.calls[0][0].message).toContain("docker compose up -d");
    expect(notify.mock.calls[0][0].message).toContain("git pull");
  });
});
