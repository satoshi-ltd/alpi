import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({ invoke: (...args) => invokeMock(...args) }));

import RunsButton from "./RunsButton.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };

beforeEach(() => invokeMock.mockReset());

it("lists durable runs and cancels an active one", async () => {
  invokeMock
    .mockResolvedValueOnce({ runs: [{ id: "r1", status: "running", source: "user", model: "m", event_count: 3 }] })
    .mockResolvedValueOnce({ cancelled: true })
    .mockResolvedValueOnce({ runs: [{ id: "r1", status: "interrupted", event_count: 5 }] });
  render(<RunsButton profile="doc" connectionId="c1" />);
  fireEvent.click(screen.getByText("Runs"));
  await waitFor(() => expect(screen.getByText(/r1/)).toBeTruthy());
  fireEvent.click(screen.getByText(/r1/));
  await waitFor(() => expect(invokeMock).toHaveBeenCalledWith("run_cancel", {
    profile: "doc", id: "r1", connectionId: "c1",
  }));
});

it("surfaces an unavailable daemon instead of claiming there are no runs", async () => {
  invokeMock.mockRejectedValueOnce(new Error("method-not-found"));
  render(<RunsButton profile="doc" connectionId="c1" />);

  fireEvent.click(screen.getByText("Runs"));

  await waitFor(() => expect(screen.getByText("Runs unavailable")).toBeTruthy());
});

it("contains cancellation failures", async () => {
  invokeMock
    .mockResolvedValueOnce({ runs: [{ id: "r1", status: "running" }] })
    .mockRejectedValueOnce(new Error("offline"));
  render(<RunsButton profile="doc" connectionId="c1" />);
  fireEvent.click(screen.getByText("Runs"));
  await waitFor(() => expect(screen.getByText(/r1/)).toBeTruthy());

  fireEvent.click(screen.getByText(/r1/));

  await waitFor(() => expect(screen.getByText("Could not stop run")).toBeTruthy());
});
