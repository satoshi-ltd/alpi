import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";

import { StorageField, _clearStorageCache } from "./maintenance.jsx";

beforeEach(() => {
  _clearStorageCache();
  invoke.mockReset();
});

describe("StorageField", () => {
  it("routes storage reads to the selected connection", async () => {
    invoke.mockResolvedValueOnce([]);
    render(
      <StorageField
        profile={{ name: "doc" }}
        activeConnection={{ id: "casa", kind: "remote" }}
      />,
    );
    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("profile_storage", {
        profile: "doc",
        connectionId: "casa",
      });
    });
  });

  it("renders cached storage immediately while refreshing", async () => {
    invoke
      .mockResolvedValueOnce([{ key: "sessions", label: "sessions", size_bytes: 12, file_count: 1 }])
      .mockResolvedValueOnce([{ key: "logs", label: "logs", size_bytes: 24, file_count: 2 }]);
    const first = render(
      <StorageField
        profile={{ name: "doc" }}
        activeConnection={{ id: "casa", kind: "remote" }}
      />,
    );
    expect(await screen.findByText("sessions")).toBeInTheDocument();
    first.unmount();

    render(
      <StorageField
        profile={{ name: "doc" }}
        activeConnection={{ id: "casa", kind: "remote" }}
      />,
    );
    expect(screen.getByText("sessions")).toBeInTheDocument();
    expect(await screen.findByText("logs")).toBeInTheDocument();
    expect(invoke).toHaveBeenCalledTimes(2);
  });
});
