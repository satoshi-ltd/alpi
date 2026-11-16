import { readFileSync } from "node:fs";
import { join } from "node:path";
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
  it("lists the fallbacks in order, one right-aligned line each", () => {
    const { container } = render(<FallbackModelsField profile={PROFILE} />);
    const lines = [...container.querySelectorAll("[data-field-line]")];
    expect(lines).toHaveLength(3);
    expect(lines[0].contains(screen.getByText("1 · sonnet"))).toBe(true);
    expect(lines[1].contains(screen.getByText("2 · gpt-x"))).toBe(true);
    expect(lines[2].childNodes).toHaveLength(0);
    expect(lines.every((l) => l.parentElement === container)).toBe(true);
    expect(container.querySelector("[class*=stackedField]")).toBeNull();
  });

  it("reads none beside Add on one line when the list is empty", () => {
    const { container } = render(<FallbackModelsField profile={{ ...PROFILE, fallback_models: [] }} />);
    const lines = [...container.querySelectorAll("[data-field-line]")];
    expect(lines).toHaveLength(1);
    expect(lines[0].contains(screen.getByText("none"))).toBe(true);
    expect(lines[0].contains(screen.getByRole("button", { name: /Add/ }))).toBe(true);
  });

  it("keeps Add on the row's edge and opens its list leftwards from it", () => {
    render(<FallbackModelsField profile={{ ...PROFILE, fallback_models: [] }} />);
    expect(screen.getByRole("button", { name: /Add/ }).hasAttribute("data-filled")).toBe(true);
    const css = readFileSync(join(import.meta.dirname, "..", "..", "..", "primitives", "ModelPicker.module.css"), "utf8");
    const down = css.match(/\.modelPickerPopDown\s*\{([^}]*)\}/)[1];
    expect(down).toMatch(/right:\s*0/);
    expect(down).not.toMatch(/left:/);
    fireEvent.click(screen.getByRole("button", { name: /Add/ }));
    expect(screen.getByRole("listbox").parentElement.style.transformOrigin).toBe("top right");
  });

  it("keeps a model's buttons together beside a label that truncates", () => {
    render(<FallbackModelsField profile={PROFILE} />);
    const label = screen.getByText("1 · sonnet");
    expect(label.className).toMatch(/fallbackLabel/);
    const actions = screen.getByRole("button", { name: "Remove sonnet" }).closest("[class*=fallbackActions]");
    expect(actions.querySelectorAll("button")).toHaveLength(3);
    const settings = readFileSync(join(import.meta.dirname, "..", "Settings.module.css"), "utf8");
    expect(settings.match(/\.fallbackLabel\s*\{([^}]*)\}/)[1]).toMatch(/text-overflow:\s*ellipsis/);
    expect(settings.match(/\.fallbackActions\s*\{([^}]*)\}/)[1]).toMatch(/flex:\s*none/);
  });

  it("leaves the hint to the row's label", () => {
    render(<FallbackModelsField profile={PROFILE} />);
    expect(screen.queryByText("Tried in order when the main model's provider fails.")).toBeNull();
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
