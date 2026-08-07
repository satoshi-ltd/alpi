import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const invokeMock = vi.fn();
const notifyMock = vi.fn();

vi.mock("@tauri-apps/api/core", () => ({ invoke: (...args) => invokeMock(...args) }));
vi.mock("../../../primitives/Notification.jsx", () => ({ useNotify: () => notifyMock }));

import {
  NetworkAddressField,
  PairingNameField,
  PrivateRouteField,
  PublicRouteField,
  _resetNetworkStatus,
} from "./network.jsx";

const baseStatus = {
  candidates: {},
  host_in_use: "100.114.140.25",
  port: 49200,
  port_source: "default",
  device_name: "MacBook-Pro",
  endpoints: [{ label: "Direct", url: "ws://100.114.140.25:49200" }],
  configured_endpoints: [],
  is_endpoints_override: false,
};

beforeEach(() => {
  invokeMock.mockReset();
  notifyMock.mockReset();
  _resetNetworkStatus();
});

describe("network settings fields", () => {
  it.each([
    ["address", (onLoadingChange) => (
      <NetworkAddressField
        profile={{ name: "default", advertise_host: "" }}
        onLoadingChange={onLoadingChange}
      />
    )],
    ["name", (onLoadingChange) => <PairingNameField onLoadingChange={onLoadingChange} />],
    ["private route", (onLoadingChange) => <PrivateRouteField onLoadingChange={onLoadingChange} />],
    ["public route", (onLoadingChange) => <PublicRouteField onLoadingChange={onLoadingChange} />],
  ])("%s reports loading to the settings progress bar", async (_, renderField) => {
    invokeMock.mockResolvedValueOnce(baseStatus);
    const onLoadingChange = vi.fn();
    render(renderField(onLoadingChange));

    await waitFor(() => expect(onLoadingChange).toHaveBeenCalledWith(true));
    await waitFor(() => expect(onLoadingChange).toHaveBeenLastCalledWith(false));
  });

  it("coalesces the network fields' mount probes into one network_status call", async () => {
    invokeMock.mockResolvedValue(baseStatus);
    render(
      <>
        <NetworkAddressField profile={{ name: "default", advertise_host: "" }} />
        <PairingNameField />
        <PrivateRouteField />
        <PublicRouteField />
      </>,
    );

    await waitFor(() => {
      const statusCalls = invokeMock.mock.calls.filter((call) => call[0] === "network_status");
      expect(statusCalls).toHaveLength(1);
    });
  });

  it("shows address and port together without a network-provider label", async () => {
    invokeMock.mockResolvedValue({ ...baseStatus, scope_in_use: "tailscale" });

    render(<NetworkAddressField profile={{ name: "default", advertise_host: "" }} />);

    expect(await screen.findByText("100.114.140.25")).toBeInTheDocument();
    expect(screen.getByText(":49200")).toBeInTheDocument();
    expect(screen.getByText("Edit")).toBeInTheDocument();
    expect(screen.queryByText(/tailscale:/i)).toBeNull();
  });

  it("edits the address row port and explicitly restarts the daemon", async () => {
    invokeMock.mockImplementation((command) => {
      if (command === "network_status") return Promise.resolve(baseStatus);
      if (command === "port_available") return Promise.resolve(true);
      return Promise.resolve({ ok: true });
    });

    render(<NetworkAddressField profile={{ name: "default", advertise_host: "" }} />);

    await screen.findByText(":49200");
    fireEvent.click(screen.getByText("Edit"));
    fireEvent.change(screen.getByRole("textbox", { name: "Host listen port" }), {
      target: { value: "49201" },
    });

    await waitFor(() => expect(invokeMock).toHaveBeenCalledWith(
      "port_available", { host: "0.0.0.0", port: 49201 },
    ));
    fireEvent.click(screen.getByText("Save and restart"));

    await waitFor(() => expect(invokeMock).toHaveBeenCalledWith(
      "set_config_field",
      { profile: "default", key: "host.tcp_port", value: "49201" },
    ));
    expect(invokeMock).toHaveBeenCalledWith("network_restart_host_server");
  });

  it("does not offer a port edit when the environment owns it", async () => {
    invokeMock.mockResolvedValue({
      ...baseStatus,
      port: 49202,
      port_source: "environment",
      endpoints: [{ label: "Direct", url: "ws://100.114.140.25:49202" }],
    });

    render(<NetworkAddressField profile={{ name: "default", advertise_host: "" }} />);

    expect(await screen.findByText(":49202")).toBeInTheDocument();
    expect(screen.queryByText("Edit")).toBeNull();
  });

  it("edits the instance name without restarting the daemon", async () => {
    invokeMock.mockImplementation((command) => {
      if (command === "network_status") return Promise.resolve(baseStatus);
      return Promise.resolve({ ok: true, restart_needed: false });
    });

    render(<PairingNameField />);

    await screen.findByText("MacBook-Pro");
    fireEvent.click(screen.getByText("Edit"));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Studio" } });
    fireEvent.click(screen.getByText("Save"));

    await waitFor(() => expect(invokeMock).toHaveBeenCalledWith(
      "network_set_advertised", { deviceName: "Studio" },
    ));
    expect(invokeMock).not.toHaveBeenCalledWith("network_restart_host_server");
  });

  it("shows the private route without an automatic or disable control", async () => {
    invokeMock.mockResolvedValue(baseStatus);

    render(<PrivateRouteField />);

    expect(await screen.findByText("ws://100.114.140.25:49200")).toBeInTheDocument();
    expect(screen.queryByText(/automatic/i)).toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("adds and removes one optional public WSS route", async () => {
    let status = baseStatus;
    invokeMock.mockImplementation((command, args) => {
      if (command === "network_status") return Promise.resolve(status);
      if (command === "network_set_advertised") {
        const publicRoute = args.endpoints[0] || null;
        status = {
          ...baseStatus,
          endpoints: publicRoute ? [publicRoute, ...baseStatus.endpoints] : baseStatus.endpoints,
          is_endpoints_override: Boolean(publicRoute),
        };
      }
      return Promise.resolve({ ok: true });
    });

    render(<PublicRouteField />);

    await screen.findByText("off");
    fireEvent.click(screen.getByText("Add"));
    fireEvent.change(screen.getByRole("textbox", { name: "Public WSS route" }), {
      target: { value: "wss://client.example.com" },
    });
    fireEvent.click(screen.getByText("Save"));

    await waitFor(() => expect(invokeMock).toHaveBeenCalledWith(
      "network_set_advertised",
      { endpoints: [{ label: "Public", url: "wss://client.example.com" }] },
    ));
    await screen.findByText("wss://client.example.com");
    fireEvent.click(screen.getByText("Remove"));
    expect(invokeMock).not.toHaveBeenCalledWith(
      "network_set_advertised", { endpoints: [] },
    );
    fireEvent.click(screen.getAllByRole("button", { name: "Remove" }).at(-1));

    await waitFor(() => expect(invokeMock).toHaveBeenCalledWith(
      "network_set_advertised", { endpoints: [] },
    ));
  });

  it("rejects plaintext public routes", async () => {
    invokeMock.mockResolvedValue(baseStatus);
    render(<PublicRouteField />);

    await screen.findByText("off");
    fireEvent.click(screen.getByText("Add"));
    fireEvent.change(screen.getByRole("textbox", { name: "Public WSS route" }), {
      target: { value: "ws://192.168.1.20:49200" },
    });

    expect(screen.getByText(/complete wss:\/\/ URL/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("removes public WSS without deleting an explicit private route", async () => {
    invokeMock.mockImplementation((command) => {
      if (command === "network_status") return Promise.resolve({
        ...baseStatus,
        endpoints: [
          { label: "Public", url: "wss://client.example.com" },
          { label: "Office", url: "ws://192.168.1.20:49200" },
        ],
        configured_endpoints: [
          { label: "Public", url: "wss://client.example.com" },
          { label: "Office", url: "ws://192.168.1.20:49200" },
        ],
        is_endpoints_override: true,
      });
      return Promise.resolve({ ok: true });
    });

    render(<PublicRouteField />);

    await screen.findByText("wss://client.example.com");
    fireEvent.click(screen.getByText("Remove"));
    fireEvent.click(screen.getAllByRole("button", { name: "Remove" }).at(-1));

    await waitFor(() => expect(invokeMock).toHaveBeenCalledWith(
      "network_set_advertised",
      { endpoints: [{ label: "Office", url: "ws://192.168.1.20:49200" }] },
    ));
  });

  it("reports route setup as unavailable against an older daemon", async () => {
    invokeMock.mockResolvedValue({
      candidates: {}, host_in_use: "100.64.0.1", port: 49200, device_name: "desk",
    });

    render(
      <>
        <PrivateRouteField />
        <PublicRouteField />
      </>,
    );

    expect(await screen.findAllByText("restart required")).toHaveLength(2);
    expect(screen.queryByText("Add")).toBeNull();
  });

  it("asks for a restart when an old daemon replaces private WS with public WSS", async () => {
    invokeMock.mockResolvedValue({
      candidates: {},
      host_in_use: "100.114.140.25",
      port: 49200,
      device_name: "desk",
      endpoints: [{ label: "Public", url: "wss://client.example.com" }],
      is_endpoints_override: true,
    });

    render(<PrivateRouteField />);

    expect(await screen.findByText("restart required")).toBeInTheDocument();
    expect(screen.queryByText("unavailable")).toBeNull();
  });

  it("refreshes the private row when public WSS is removed", async () => {
    let status = {
      candidates: {},
      host_in_use: "100.114.140.25",
      port: 49200,
      device_name: "desk",
      endpoints: [{ label: "Public", url: "wss://client.example.com" }],
      is_endpoints_override: true,
    };
    invokeMock.mockImplementation((command) => {
      if (command === "network_status") return Promise.resolve(status);
      if (command === "network_set_advertised") status = baseStatus;
      return Promise.resolve({ ok: true });
    });

    render(
      <>
        <PrivateRouteField />
        <PublicRouteField />
      </>,
    );

    expect(await screen.findByText("restart required")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Remove"));
    fireEvent.click(screen.getAllByRole("button", { name: "Remove" }).at(-1));

    expect(await screen.findByText("ws://100.114.140.25:49200")).toBeInTheDocument();
    expect(screen.getByText("off")).toBeInTheDocument();
  });

  it("keeps the public route when removal is cancelled", async () => {
    invokeMock.mockResolvedValue({
      ...baseStatus,
      endpoints: [
        { label: "Public", url: "wss://client.example.com" },
        ...baseStatus.endpoints,
      ],
      configured_endpoints: [{ label: "Public", url: "wss://client.example.com" }],
      is_endpoints_override: true,
    });

    render(<PublicRouteField />);

    await screen.findByText("wss://client.example.com");
    fireEvent.click(screen.getByText("Remove"));
    expect(screen.getByText("Remove public route?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(invokeMock).not.toHaveBeenCalledWith(
      "network_set_advertised", { endpoints: [] },
    );
    expect(screen.queryByText("Remove public route?")).toBeNull();
  });
});
