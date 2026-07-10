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
  it("prefers a picker override over session and profile", () => {
    expect(pickEffectiveModel("over/ride", "sess/ion", "prof/ile")).toBe("over/ride");
  });

  it("uses the session's model when there is no override", () => {
    expect(pickEffectiveModel(null, "sess/ion", "prof/ile")).toBe("sess/ion");
  });

  it("falls back to the profile's model when neither is set", () => {
    expect(pickEffectiveModel(null, undefined, "prof/ile")).toBe("prof/ile");
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

describe("ChatPane — header reflects the effective model", () => {
  it("resolves and shows the session's model, with its own context denominator", async () => {
    invoke.mockImplementation(async (cmd) =>
      cmd === "resolve_ctx_window" ? 480000 : null,
    );
    renderPane(
      { name: "a", model: "prof/ile" },
      { turns: [{ user: "hi", assistant: "yo", at: 0 }], last_ctx_tokens: 0, model: "sess/ion" },
    );
    await waitFor(() =>
      expect(invoke).toHaveBeenCalledWith("resolve_ctx_window", {
        profile: "a",
        model: "sess/ion",
      }),
    );
    expect(screen.getByText("sess/ion")).toBeTruthy();
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
    expect(screen.getByText("prof/ile")).toBeTruthy();
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
    expect(screen.getByText("prov/base")).toBeTruthy();

    fireEvent.click(screen.getByText("base").closest("button"));
    fireEvent.click(screen.getByText("other"));
    await waitFor(() => expect(screen.getByText("prov/other")).toBeTruthy());

    rerender(paneEl("B"));
    await waitFor(() => expect(screen.getByText("prov/base")).toBeTruthy());
    expect(screen.queryByText("prov/other")).toBeNull();
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
