import { render, screen, waitFor, act } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({ invoke: (...a) => invokeMock(...a) }));

import SessionsButton from "./SessionsButton.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };

const sessA = [{ id: "a1", kind: "chat", first_user: "hello from A", updated_at: 1780000000 }];
const sessB = [{ id: "b1", kind: "chat", first_user: "hello from B", updated_at: 1780000000 }];

beforeEach(() => invokeMock.mockReset());

describe("SessionsButton — profile switch", () => {
  it("hides the previous profile's sessions until the new profile's fetch resolves", async () => {
    invokeMock.mockResolvedValueOnce(sessA);
    const { rerender } = render(<SessionsButton profile="A" />);
    await waitFor(() => expect(screen.getByText("Sessions")).toBeTruthy());

    let resolveB;
    invokeMock.mockImplementationOnce(() => new Promise((r) => { resolveB = r; }));
    rerender(<SessionsButton profile="B" />);
    expect(screen.queryByText("Sessions")).toBeNull();

    await act(async () => { resolveB(sessB); });
    await waitFor(() => expect(screen.getByText("Sessions")).toBeTruthy());
  });
});
