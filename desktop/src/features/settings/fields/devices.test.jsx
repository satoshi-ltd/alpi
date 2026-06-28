import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";

const { notifyMock } = vi.hoisted(() => ({ notifyMock: vi.fn() }));

vi.mock("../../../primitives/Notification.jsx", () => ({
  useNotify: () => notifyMock,
}));

import { DevicesField, _clearDevicesCache } from "./devices.jsx";

beforeEach(() => {
  _clearDevicesCache();
  invoke.mockReset();
  notifyMock.mockReset();
});

describe("DevicesField", () => {
  it("fetches the selected connection explicitly", async () => {
    invoke.mockImplementation(async (command) => {
      if (command === "devices_list") return [];
      return null;
    });
    render(<DevicesField connectionId="casa" />);
    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("devices_list", { connectionId: "casa" });
    });
  });

  it("reports loading while the selected daemon is being fetched", async () => {
    let resolve;
    const onLoadingChange = vi.fn();
    invoke.mockReturnValueOnce(new Promise((done) => { resolve = done; }));
    render(
      <DevicesField
        connectionId="casa"
        role="admin"
        onLoadingChange={onLoadingChange}
      />,
    );
    expect(onLoadingChange).toHaveBeenCalledWith(true);
    await act(async () => {
      resolve([]);
      await Promise.resolve();
    });
    await waitFor(() => expect(onLoadingChange).toHaveBeenLastCalledWith(false));
  });

  it("clears old rows and ignores a late response after switching daemons", async () => {
    let resolveCasa;
    const casa = new Promise((resolve) => { resolveCasa = resolve; });
    invoke.mockImplementation((command, args) => {
      if (command !== "devices_list") return Promise.resolve(null);
      if (args?.connectionId === "casa") return casa;
      if (args?.connectionId === "mirai") {
        return Promise.resolve([{ token_id: "mirai-1", label: "Mirai phone" }]);
      }
      return Promise.resolve([]);
    });

    const { rerender } = render(<DevicesField connectionId="casa" role="admin" />);
    rerender(<DevicesField connectionId="mirai" role="admin" />);
    fireEvent.click(await screen.findByRole("button", { name: /1 device/i }));
    expect(await screen.findByText("Mirai phone")).toBeInTheDocument();

    await act(async () => {
      resolveCasa([{ token_id: "casa-1", label: "Casa phone" }]);
      await Promise.resolve();
    });
    expect(screen.queryByText("Casa phone")).toBeNull();
    expect(screen.getByText("Mirai phone")).toBeInTheDocument();
  });

  it("renders cached devices immediately while refreshing", async () => {
    invoke
      .mockResolvedValueOnce([{ token_id: "casa-1", label: "Casa phone" }])
      .mockResolvedValueOnce([{ token_id: "casa-2", label: "Casa tablet" }]);
    const first = render(<DevicesField connectionId="casa" role="admin" />);
    fireEvent.click(await screen.findByRole("button", { name: /1 device/i }));
    expect(await screen.findByText("Casa phone")).toBeInTheDocument();
    first.unmount();

    render(<DevicesField connectionId="casa" role="admin" />);
    expect(screen.getByRole("button", { name: /1 device/i })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: /1 device/i })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /1 device/i }));
    expect(await screen.findByText("Casa tablet")).toBeInTheDocument();
    expect(invoke).toHaveBeenCalledTimes(2);
  });
});
