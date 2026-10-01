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

  it("names the manual step for the install kind a daemon without self_update answers with", async () => {
    invoke.mockResolvedValue({ updated: false, reason: "manual", installer: "docker", latest: "0.16.19" });
    render(<DaemonField connectionId="local" />);

    fireEvent.click(screen.getByRole("button", { name: "Update alpi" }));

    await waitFor(() => expect(notify).toHaveBeenCalledWith(expect.objectContaining({
      message: expect.stringContaining("Set the image tag to 0.16.19 in docker-compose.yml"),
    })));
  });

  it("keeps explaining both paths when an older daemon only says dev", async () => {
    invoke.mockResolvedValue({ updated: false, reason: "manual", installer: "dev" });
    render(<DaemonField connectionId="local" />);

    fireEvent.click(screen.getByRole("button", { name: "Update alpi" }));

    await waitFor(() => expect(notify).toHaveBeenCalled());
    expect(notify.mock.calls[0][0].message).toContain("docker compose up -d");
    expect(notify.mock.calls[0][0].message).toContain("git pull");
  });

  it("offers no update button where the daemon cannot update itself", () => {
    render(<DaemonField connectionId="docker-box" selfUpdate={false} />);

    expect(screen.queryByRole("button", { name: "Update alpi" })).toBeNull();
    expect(screen.getByRole("button", { name: "Restart daemon" })).toBeTruthy();
  });
});
