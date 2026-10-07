import { render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn(() => new Promise(() => {})) }));
vi.mock("../../primitives/Notification.jsx", () => ({ useNotify: () => vi.fn() }));
vi.mock("../../hooks/useProfileDetail.js", () => ({
  useProfileDetail: () => ({ detail: null, loading: true, refresh: vi.fn() }),
}));
vi.mock("../../hooks/useUsage.js", () => ({
  useUsageDaily: () => ({ days: [], loading: true }),
}));

import ProfileDetail from "./ProfileDetail.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
globalThis.Element.prototype.scrollTo ??= () => {};

const liveRegions = (root) => [...root.querySelectorAll("[role=status], [aria-live], [role=progressbar]")]
  .filter((n) => !n.hasAttribute("aria-valuenow"));

describe("profile settings while everything loads", () => {
  it("speaks through one live region and draws every leaf wait as a named image", async () => {
    const { container } = render(
      <ProfileDetail
        profile={{ name: "default", accent: "#10b981", budget: 2 }}
        profiles={[{ name: "default", accent: "#10b981" }]}
        activeConnection={{ id: "local", kind: "local" }}
        connectionSyncing
      />,
    );
    await waitFor(() => expect(container.querySelectorAll("[role=img][aria-label^=Loading]").length).toBeGreaterThan(2));
    expect(liveRegions(container).length).toBeLessThanOrEqual(1);
    expect(container.textContent).not.toMatch(/loading/i);
  });
});
