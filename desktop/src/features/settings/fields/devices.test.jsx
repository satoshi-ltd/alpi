import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";

const { notifyMock } = vi.hoisted(() => ({ notifyMock: vi.fn() }));

vi.mock("../../../primitives/Notification.jsx", () => ({
  useNotify: () => notifyMock,
}));

import { DevicesField, PairDeviceModal, _clearDevicesCache } from "./devices.jsx";

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

describe("PairDeviceModal", () => {
  it("includes the stable server connection id in the pairing link", async () => {
    invoke.mockImplementation((command) => {
      if (command === "profile_summaries") return Promise.resolve([]);
      if (command === "devices_generate") {
        return Promise.resolve({
          connection_id: "conn-1",
          pairing_id: "pair-1",
          pairing_token: "grant",
          pairing_status: "pending",
          expires_at: 1_800_000_000,
          url: "wss://client.example.com",
          endpoints: [{ label: "Public", url: "wss://client.example.com" }],
        });
      }
      return Promise.resolve(null);
    });

    render(<PairDeviceModal onClose={() => {}} onPaired={() => {}} />);

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Phone" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate pairing code" }));

    expect(await screen.findByText(/connection_id=conn-1/)).toBeInTheDocument();
    expect(screen.getByText(/pairing_token=grant/)).toBeInTheDocument();
  });

  it("describes a consumed grant without claiming the client saved it", async () => {
    invoke.mockImplementation((command) => {
      if (command === "profile_summaries") return Promise.resolve([]);
      if (command === "devices_generate") {
        return Promise.resolve({
          connection_id: "conn-1",
          pairing_id: "pair-1",
          pairing_token: "grant",
          pairing_status: "consumed",
          expires_at: 1_800_000_000,
          url: "wss://client.example.com",
          endpoints: [{ label: "Public", url: "wss://client.example.com" }],
        });
      }
      return Promise.resolve(null);
    });

    render(<PairDeviceModal onClose={() => {}} onPaired={() => {}} />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Phone" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate pairing code" }));

    expect(await screen.findByText("code used · verify the client connected"))
      .toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(notifyMock).toHaveBeenCalledWith(expect.objectContaining({
      message: expect.stringContaining("Pairing code used"),
    }));
    const messages = notifyMock.mock.calls.map(([value]) => value?.message || "");
    expect(messages).not.toContain('Device "Phone" paired');
  });

  it("shows the WSS requirement when the configured address is a hostname", async () => {
    invoke.mockImplementation((command) => {
      if (command === "profile_summaries") return Promise.resolve([]);
      if (command === "devices_generate") {
        return Promise.reject(new Error(
          "alp -32010: no-advertised-host — Cannot pair: 'box.tail1234.ts.net' is a hostname. Configure a certificate-validated wss:// URL in host.endpoints.",
        ));
      }
      return Promise.resolve(null);
    });

    render(<PairDeviceModal onClose={() => {}} onPaired={() => {}} />);

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "Phone" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Generate pairing code" }));

    expect(await screen.findByText(/box\.tail1234\.ts\.net.*wss:\/\//i))
      .toBeInTheDocument();
    expect(notifyMock).not.toHaveBeenCalled();
  });

  it("portals the profile selector outside the scrollable modal content", async () => {
    invoke.mockImplementation((command) => {
      if (command === "profile_summaries") {
        return Promise.resolve([
          { name: "default", accent: "#d6aa45" },
          { name: "atlas", accent: "#22c55e" },
        ]);
      }
      return Promise.resolve(null);
    });

    render(<PairDeviceModal onClose={() => {}} onPaired={() => {}} />);

    const trigger = await screen.findByRole("button", { name: "All profiles" });
    vi.spyOn(trigger, "getBoundingClientRect").mockReturnValue({
      bottom: 200,
      height: 60,
      left: 140,
      right: 780,
      top: 140,
      width: 640,
      x: 140,
      y: 140,
      toJSON: () => ({}),
    });
    const modal = screen.getByText("Pair a new device").parentElement.parentElement;
    fireEvent.click(trigger);
    const option = await screen.findByRole("button", { name: /Restrict to/i });
    const menu = option.parentElement.parentElement;

    expect(modal).not.toContainElement(option);
    expect(document.body).toContainElement(option);
    expect(menu).toHaveStyle({ width: "640px" });
  });
});
