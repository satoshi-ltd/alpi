import { beforeEach, describe, it, expect, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";

import ChatPane from "./ChatPane.jsx";
import { pickEffectiveModel } from "../lib/effectiveModel.js";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
globalThis.Element.prototype.scrollTo ??= () => {};

beforeEach(() => {
  vi.resetAllMocks();
});

describe("pickEffectiveModel", () => {
  it("prefers a picker override over the profile", () => {
    expect(pickEffectiveModel("over/ride", "prof/ile")).toBe("over/ride");
  });

  it("falls back to the profile's current model", () => {
    expect(pickEffectiveModel(null, "prof/ile")).toBe("prof/ile");
  });
});

function renderPane(profile, sessionData) {
  return render(
    <ChatPane
      view={{ kind: "profile", profile: profile.name, sessionId: "s1" }}
      profiles={[profile]}
      activeProfile={profile}
      sessionData={sessionData}
      onSend={vi.fn()}
      onRewriteMessage={vi.fn()}
      onRetryMessage={vi.fn()}
    />,
  );
}

describe("ChatPane — header reflects the next turn's model", () => {
  it("shows the current profile model when an old session records another model", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "resolve_ctx_window") return 480000;
      if (cmd === "ollama_models") return [];
      return null;
    });
    renderPane(
      {
        name: "a",
        model: "openrouter/deepseek/deepseek-v4-flash-latest",
        models: [
          "openrouter/deepseek/deepseek-v4-flash-latest",
          "openrouter/deepseek/deepseek-v4-pro",
        ],
      },
      {
        turns: [{ user: "hi", assistant: "yo", at: 0 }],
        last_ctx_tokens: 0,
        model: "openrouter/deepseek/deepseek-v4-flash-0731",
      },
    );
    await waitFor(() =>
      expect(invoke).toHaveBeenCalledWith("resolve_ctx_window", {
        profile: "a",
        model: "openrouter/deepseek/deepseek-v4-flash-latest",
      }),
    );
    expect(screen.getAllByText("deepseek-v4-flash-latest")).toHaveLength(2);
    expect(screen.getAllByText("openrouter/deepseek/deepseek-v4-flash-latest")).toHaveLength(2);
    expect(screen.queryByTitle("openrouter/deepseek/deepseek-v4-flash-latest")).toBeNull();
    expect(screen.queryByText(/flash-0731/)).toBeNull();
    await waitFor(() => expect(screen.getAllByText(/480K/).length).toBeGreaterThan(0));
  });

  it("falls back to the profile's model when the session has none", async () => {
    invoke.mockImplementation(async (cmd) =>
      cmd === "resolve_ctx_window" ? 367232 : null,
    );
    renderPane(
      { name: "a", model: "prof/ile" },
      { turns: [{ user: "hi", assistant: "yo", at: 0 }], last_ctx_tokens: 0 },
    );
    await waitFor(() =>
      expect(invoke).toHaveBeenCalledWith("resolve_ctx_window", {
        profile: "a",
        model: "prof/ile",
      }),
    );
    expect(screen.getByText("ile")).toBeTruthy();
  });
});

describe("ChatPane — model override is connection-scoped", () => {
  const profile = {
    name: "a",
    model: "prov/base",
    models: ["prov/base", "prov/other"],
  };
  const sessionData = {
    turns: [{ user: "hi", assistant: "yo", at: 0 }],
    last_ctx_tokens: 0,
  };

  function paneEl(connectionId) {
    return (
      <ChatPane
        view={{ kind: "profile", profile: "a", sessionId: "s1" }}
        profiles={[profile]}
        activeProfile={profile}
        connectionId={connectionId}
        sessionData={sessionData}
        onSend={vi.fn()}
        onRewriteMessage={vi.fn()}
        onRetryMessage={vi.fn()}
      />
    );
  }

  it("drops a manual override when switching to another daemon with the same profile/session/model", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "ollama_models") return [];
      if (cmd === "resolve_ctx_window") return 400000;
      return null;
    });
    const { rerender } = render(paneEl("A"));
    expect(screen.getAllByText("base").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: /base/ }));
    fireEvent.click(screen.getByText("other"));
    await waitFor(() => expect(screen.getAllByText("other").length).toBeGreaterThan(0));

    rerender(paneEl("B"));
    await waitFor(() => expect(screen.getAllByText("base").length).toBeGreaterThan(0));
    expect(screen.queryByText("other")).toBeNull();
  });
});

describe("ChatPane — per-turn model badge", () => {
  it("shows the routed model when a turn ran on a different model than the profile", () => {
    invoke.mockImplementation(async () => null);
    renderPane(
      { name: "a", model: "openrouter/main" },
      {
        turns: [
          { user: "hi", assistant: "rescued", at: 0, model: "openrouter/deep" },
        ],
      },
    );
    const badge = screen.getByTitle("Ran on openrouter/deep");
    expect(badge.textContent).toBe("deep");
  });

  it("uses the session's model as baseline, not the profile's current one", () => {
    invoke.mockImplementation(async () => null);
    renderPane(
      { name: "a", model: "openrouter/new-default" },
      {
        model: "openrouter/old-default",
        turns: [
          { user: "hi", assistant: "historic reply", at: 0, model: "openrouter/old-default" },
          { user: "hard", assistant: "escalated reply", at: 1, model: "openrouter/deep" },
        ],
      },
    );
    // Same model as the session baseline: no badge even though the profile default changed since.
    expect(screen.queryByTitle("Ran on openrouter/old-default")).toBeNull();
    expect(screen.getByTitle("Ran on openrouter/deep")).toBeTruthy();
  });

  it("hides the badge when the turn ran on the profile model", () => {
    invoke.mockImplementation(async () => null);
    renderPane(
      { name: "a", model: "openrouter/main" },
      {
        turns: [
          { user: "hi", assistant: "yo", at: 0, model: "openrouter/main" },
          { user: "old", assistant: "turn without model", at: 1 },
        ],
      },
    );
    expect(screen.queryByTitle(/^Ran on /)).toBeNull();
  });
});
