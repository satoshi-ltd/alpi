import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";

const h = vi.hoisted(() => ({ invoke: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => ({ invoke: h.invoke }));
vi.mock("../../../primitives/Notification.jsx", () => ({ useNotify: () => () => {} }));

import { TierField } from "./TierField.jsx";

beforeEach(() => {
  h.invoke.mockReset();
  h.invoke.mockResolvedValue([]);
});

const PROFILE = {
  name: "work",
  models: ["openrouter/main", "openrouter/flash"],
  tiers: {
    fast: { model: "openrouter/flash", effort: "low", reasoning_supported: true },
    deep: { model: "", effort: "", reasoning_supported: false },
  },
};

describe("TierField", () => {
  it("picking a model persists tiers.<name>.model via set_config_field", async () => {
    render(<TierField profile={PROFILE} name="deep" onSaved={() => {}} />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { expanded: false }));
    });
    await act(async () => {
      fireEvent.click(screen.getByText("main"));
    });
    expect(h.invoke).toHaveBeenCalledWith("set_config_field", {
      profile: "work",
      key: "tiers.deep.model",
      value: "openrouter/main",
    });
  });

  it("configured tier shows effort control and Clear unsets the whole tier", async () => {
    const onSaved = vi.fn();
    render(<TierField profile={PROFILE} name="fast" onSaved={onSaved} />);
    expect(screen.getByText("Low")).toBeTruthy();
    await act(async () => {
      fireEvent.click(screen.getByText("Clear"));
    });
    expect(h.invoke).toHaveBeenCalledWith("unset_config_field", {
      profile: "work",
      key: "tiers.fast",
    });
    expect(onSaved).toHaveBeenCalled();
  });

  it("unset tier shows the main-model fallback hint", () => {
    render(<TierField profile={PROFILE} name="deep" onSaved={() => {}} />);
    expect(screen.getByText("uses main model")).toBeTruthy();
  });
});
