import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const h = vi.hoisted(() => ({ invoke: vi.fn(), notify: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => ({ invoke: h.invoke }));
vi.mock("../../../primitives/Notification.jsx", () => ({ useNotify: () => h.notify }));

import { FallbackModelsField } from "./FallbackModelsField.jsx";

beforeEach(() => {
  h.invoke.mockReset();
  h.notify.mockReset();
  h.invoke.mockResolvedValue([]);
});

const PROFILE = {
  name: "work",
  model: "openrouter/main",
  models: ["openrouter/main", "anthropic/sonnet", "openai/gpt-x"],
  fallback_models: ["anthropic/sonnet", "openai/gpt-x"],
};

const saved = (list) => ["set_config_field", {
  profile: "work",
  key: "fallback_models",
  value: JSON.stringify(list),
}];

describe("FallbackModelsField", () => {
  it("lists the fallbacks in order with the hint", () => {
    render(<FallbackModelsField profile={PROFILE} />);
    expect(screen.getByText("1 · sonnet")).toBeTruthy();
    expect(screen.getByText("2 · gpt-x")).toBeTruthy();
    expect(screen.getByText("Tried in order when the main model's provider fails.")).toBeTruthy();
  });

  it("reads none when the list is empty", () => {
    render(<FallbackModelsField profile={{ ...PROFILE, fallback_models: [] }} />);
    expect(screen.getByText("none")).toBeTruthy();
  });

  it("adds from the model picker without offering the main model or listed ones", async () => {
    const onSaved = vi.fn();
    render(
      <FallbackModelsField
        profile={{ ...PROFILE, models: [...PROFILE.models, "google/gem"], fallback_models: ["anthropic/sonnet"] }}
        onSaved={onSaved}
      />,
    );
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Add/ }));
    });
    const options = screen.getAllByRole("option").map((o) => o.textContent);
    expect(options).toEqual(["gpt-x", "gem"]);
    await act(async () => {
      fireEvent.click(screen.getByText("gpt-x"));
    });
    expect(h.invoke).toHaveBeenCalledWith(...saved(["anthropic/sonnet", "openai/gpt-x"]));
    expect(onSaved).toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /Add/ }).textContent).toContain("Add");
  });

  it("reorders and removes entries", async () => {
    render(<FallbackModelsField profile={PROFILE} />);
    expect(screen.getByRole("button", { name: "Move sonnet up" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Move gpt-x down" })).toBeDisabled();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Move gpt-x up" }));
    });
    expect(h.invoke).toHaveBeenLastCalledWith(...saved(["openai/gpt-x", "anthropic/sonnet"]));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Remove sonnet" }));
    });
    expect(h.invoke).toHaveBeenLastCalledWith(...saved(["openai/gpt-x"]));
  });

  it("stays busy until the refetch lands, then edits the refreshed list", async () => {
    let landed;
    const onSaved = vi.fn(() => new Promise((resolve) => { landed = resolve; }));
    const profile = { ...PROFILE, fallback_models: ["anthropic/sonnet", "openai/gpt-x", "google/gem"] };
    const { rerender } = render(<FallbackModelsField profile={profile} onSaved={onSaved} />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Remove sonnet" }));
    });
    expect(onSaved).toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Remove gem" })).toBeDisabled();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Remove gem" }));
    });
    expect(h.invoke.mock.calls.filter(([cmd]) => cmd === "set_config_field")).toHaveLength(1);
    rerender(<FallbackModelsField profile={{ ...profile, fallback_models: ["openai/gpt-x", "google/gem"] }} onSaved={onSaved} />);
    await act(async () => { landed(); });
    expect(screen.getByRole("button", { name: "Remove gem" })).not.toBeDisabled();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Remove gem" }));
    });
    expect(h.invoke).toHaveBeenLastCalledWith(...saved(["openai/gpt-x"]));
  });

  it("does not report a failed refetch as a failed save", async () => {
    render(<FallbackModelsField profile={PROFILE} onSaved={() => Promise.reject(new Error("offline"))} />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Remove sonnet" }));
    });
    expect(h.notify).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Remove gpt-x" })).not.toBeDisabled();
  });

  it("offers no Add once every model is the main one or listed", () => {
    render(<FallbackModelsField profile={PROFILE} />);
    expect(screen.queryByRole("button", { name: /Add/ })).toBeNull();
    expect(screen.getByText("Tried in order when the main model's provider fails.")).toBeTruthy();
  });

  it("leaves the main model out of every save after a fallback was promoted", async () => {
    const profile = { ...PROFILE, model: "openai/gpt-x", fallback_models: ["anthropic/sonnet", "openai/gpt-x", "google/gem"] };
    render(<FallbackModelsField profile={profile} />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Remove gem" }));
    });
    expect(h.invoke).toHaveBeenLastCalledWith(...saved(["anthropic/sonnet"]));
  });

  it("replaces Add with the cap once the list is full", () => {
    const full = Array.from({ length: 16 }, (_, i) => `p/m${i}`);
    render(<FallbackModelsField profile={{ ...PROFILE, models: [...PROFILE.models, ...full], fallback_models: full }} />);
    expect(screen.queryByRole("button", { name: /Add/ })).toBeNull();
    expect(screen.getByText("16 is the most a profile can list.")).toBeTruthy();
  });

  it("surfaces a refused save as an error toast", async () => {
    h.invoke.mockRejectedValue("fallback_models cannot include the main model");
    render(<FallbackModelsField profile={PROFILE} />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Remove gpt-x" }));
    });
    expect(h.notify).toHaveBeenCalledWith(expect.objectContaining({
      message: "fallback models: fallback_models cannot include the main model",
      variant: "error",
    }));
  });
});
