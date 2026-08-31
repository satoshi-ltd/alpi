import { render, screen, waitFor, act, fireEvent } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({ invoke: (...a) => invokeMock(...a) }));

import SessionsButton, { invalidateSessionsButtonCache } from "./SessionsButton.jsx";
import { setSessionTitle } from "../lib/session-titles.js";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };

const sessA = [{ id: "a1", kind: "chat", first_user: "hello from A", updated_at: 1780000000 }];
const sessB = [{ id: "b1", kind: "chat", first_user: "hello from B", updated_at: 1780000000 }];
const sessWithTurns = [{ id: "a1", kind: "chat", first_user: "hello from A", turn_count: 2, updated_at: 1780000000 }];

beforeEach(() => {
  invokeMock.mockReset();
  invalidateSessionsButtonCache();
  localStorage.clear();
});

describe("SessionsButton — profile switch", () => {
  it("isolates a same-named profile across two connections", async () => {
    let resolveRemote;
    invokeMock.mockImplementation((_cmd, args) => {
      if (args.connectionId === "local") return Promise.resolve(sessA);
      return new Promise((resolve) => { resolveRemote = resolve; });
    });
    const { rerender } = render(
      <SessionsButton profile="A" connectionId="local" />,
    );
    await waitFor(() => expect(screen.getByText("Sessions")).toBeTruthy());

    rerender(<SessionsButton profile="A" connectionId="remote" />);
    expect(screen.queryByText("Sessions")).toBeNull();

    await act(async () => { resolveRemote(sessB); });
    await waitFor(() => expect(screen.getByText("Sessions")).toBeTruthy());
    expect(invokeMock).toHaveBeenLastCalledWith("sessions", {
      profile: "A",
      limit: 30,
      connectionId: "remote",
    });
  });

  it("hides the previous profile's sessions until the new profile's fetch resolves", async () => {
    invokeMock.mockResolvedValue(sessA);
    const { rerender } = render(<SessionsButton profile="A" />);
    await waitFor(() => expect(screen.getByText("Sessions")).toBeTruthy());

    let resolveB;
    invokeMock.mockImplementationOnce(() => new Promise((r) => { resolveB = r; }));
    rerender(<SessionsButton profile="B" />);
    expect(screen.queryByText("Sessions")).toBeNull();

    await act(async () => { resolveB(sessB); });
    await waitFor(() => expect(screen.getByText("Sessions")).toBeTruthy());
  });

  it("paints a revisited profile's cached list instantly while revalidating", async () => {
    invokeMock.mockResolvedValue(sessA);
    const { rerender } = render(<SessionsButton profile="A" />);
    await waitFor(() => expect(screen.getByText("Sessions")).toBeTruthy());

    invokeMock.mockImplementationOnce(() => new Promise(() => {}));
    rerender(<SessionsButton profile="B" />);
    expect(screen.queryByText("Sessions")).toBeNull();

    invokeMock.mockImplementationOnce(() => new Promise(() => {}));
    rerender(<SessionsButton profile="A" />);
    expect(screen.getByText("Sessions")).toBeTruthy();
  });

  it("does not refetch when the popover closes", async () => {
    invokeMock.mockResolvedValue(sessA);
    render(<SessionsButton profile="A" />);
    await waitFor(() => expect(screen.getByText("Sessions")).toBeTruthy());
    const callsAfterMount = invokeMock.mock.calls.length;

    fireEvent.click(screen.getByText("Sessions"));
    await waitFor(() => expect(invokeMock.mock.calls.length).toBe(callsAfterMount + 1));

    fireEvent.click(screen.getByText("Sessions"));
    await act(async () => { await Promise.resolve(); });
    expect(invokeMock.mock.calls.length).toBe(callsAfterMount + 1);
  });

  it("opens the compact sessions dropdown from an external tick", async () => {
    invokeMock.mockResolvedValue(sessWithTurns);
    const { rerender } = render(<SessionsButton profile="A" openTick={0} />);
    await waitFor(() => expect(screen.getByText("Sessions")).toBeTruthy());

    expect(screen.queryByText("hello from A")).toBeNull();
    rerender(<SessionsButton profile="A" openTick={1} />);

    await waitFor(() => expect(screen.getByText("hello from A")).toBeTruthy());
    expect(screen.getByText("Manage sessions →")).toBeTruthy();
  });

  it("does not auto-open a remounted dropdown with a stale external tick", async () => {
    invokeMock.mockResolvedValue(sessWithTurns);
    render(<SessionsButton profile="A" openTick={1} />);
    await waitFor(() => expect(screen.getByText("Sessions")).toBeTruthy());

    expect(screen.queryByText("hello from A")).toBeNull();
    expect(screen.queryByText("Manage sessions →")).toBeNull();
  });

  it("shows a custom title and updates live when it changes elsewhere", async () => {
    invokeMock.mockResolvedValue(sessWithTurns);
    const { rerender } = render(<SessionsButton profile="A" openTick={0} />);
    await waitFor(() => expect(screen.getByText("Sessions")).toBeTruthy());
    rerender(<SessionsButton profile="A" openTick={1} />);
    await waitFor(() => expect(screen.getByText("hello from A")).toBeTruthy());

    act(() => { setSessionTitle(null, "A", "a1", "Renamed thread"); });

    await waitFor(() => expect(screen.getByText("Renamed thread")).toBeTruthy());
    expect(screen.queryByText("hello from A")).toBeNull();
  });

  it("owns the ⌘N advertisement as New session, the noun the sidebar uses", async () => {
    invokeMock.mockResolvedValue([]);
    const { rerender } = render(<SessionsButton profile="A" openTick={0} />);
    await waitFor(() => expect(screen.getByText("Sessions")).toBeTruthy());
    rerender(<SessionsButton profile="A" openTick={1} />);

    await waitFor(() => expect(screen.getByText("New session")).toBeTruthy());
    expect(screen.getByText("No sessions yet")).toBeTruthy();
    expect(screen.getByText("⌘")).toBeTruthy();
    expect(screen.getByText("N")).toBeTruthy();
    expect(screen.queryByText("New chat")).toBeNull();
  });

});
