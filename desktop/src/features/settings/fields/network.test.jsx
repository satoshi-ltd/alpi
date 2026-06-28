import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const invokeMock = vi.fn();

vi.mock("@tauri-apps/api/core", () => ({ invoke: (...a) => invokeMock(...a) }));
vi.mock("../../../primitives/Notification.jsx", () => ({ useNotify: () => () => {} }));

import { HostPortField, NetworkAddressField, PairingNameField, _resetNetworkStatus } from "./network.jsx";

beforeEach(() => {
  invokeMock.mockReset();
  _resetNetworkStatus();
});

describe("network settings fields", () => {
  it.each([
    ["address", (onLoadingChange) => <NetworkAddressField onLoadingChange={onLoadingChange} />],
    ["host port", (onLoadingChange) => (
      <HostPortField
        profile={{ name: "default", advertise_host: "" }}
        onLoadingChange={onLoadingChange}
      />
    )],
    ["pairing name", (onLoadingChange) => <PairingNameField onLoadingChange={onLoadingChange} />],
  ])("%s reports loading to the settings progress bar", async (_, renderField) => {
    invokeMock.mockResolvedValueOnce({
      candidates: {},
      host_in_use: "100.64.0.1",
      port: 49200,
      device_name: "desk",
    });
    const onLoadingChange = vi.fn();
    render(renderField(onLoadingChange));

    await waitFor(() => expect(onLoadingChange).toHaveBeenCalledWith(true));
    await waitFor(() => expect(onLoadingChange).toHaveBeenLastCalledWith(false));
  });

  it("coalesces the three fields' mount probes into one network_status call", async () => {
    invokeMock.mockResolvedValue({ candidates: {}, port: 49200, device_name: "desk" });
    render(
      <>
        <NetworkAddressField />
        <HostPortField profile={{ name: "default", advertise_host: "" }} />
        <PairingNameField />
      </>,
    );
    await waitFor(() => {
      const statusCalls = invokeMock.mock.calls.filter((c) => c[0] === "network_status");
      expect(statusCalls).toHaveLength(1);
    });
  });
});
