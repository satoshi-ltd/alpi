import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const h = vi.hoisted(() => ({ invoke: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => ({ invoke: h.invoke }));
vi.mock("../../../primitives/Notification.jsx", () => ({ useNotify: () => () => {} }));

import { VisionModelField } from "./VisionModelField.jsx";

beforeEach(() => {
  h.invoke.mockReset();
  h.invoke.mockResolvedValue([]);
});

const PROFILE = {
  name: "work",
  model: "openrouter/main",
  models: ["openrouter/main", "openrouter/deepseek/vision"],
  vision_model: "",
};

describe("VisionModelField", () => {
  it("persists the read_image override", async () => {
    render(<VisionModelField profile={PROFILE} />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { expanded: false }));
    });
    await act(async () => {
      fireEvent.click(screen.getByText("deepseek/vision"));
    });
    expect(h.invoke).toHaveBeenCalledWith("set_config_field", {
      profile: "work",
      key: "tools.read_image.model",
      value: "openrouter/deepseek/vision",
    });
  });

  it("clears the override back to the main model", async () => {
    const onSaved = vi.fn();
    render(
      <VisionModelField
        profile={{ ...PROFILE, vision_model: "openrouter/deepseek/vision" }}
        onSaved={onSaved}
      />,
    );
    await act(async () => {
      fireEvent.click(screen.getByText("Clear"));
    });
    expect(h.invoke).toHaveBeenCalledWith("set_config_field", {
      profile: "work",
      key: "tools.read_image.model",
      value: "",
    });
    expect(onSaved).toHaveBeenCalled();
  });

  it("makes the fallback scope explicit when unset", () => {
    render(<VisionModelField profile={PROFILE} />);
    expect(screen.getByText("read_image uses main model")).toBeTruthy();
  });
});
