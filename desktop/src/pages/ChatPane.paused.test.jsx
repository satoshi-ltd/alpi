import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import ChatPane from "./ChatPane.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
globalThis.Element.prototype.scrollTo ??= () => {};

const sessionData = { turns: [{ user: "hi", assistant: "yo", at: 0 }], last_ctx_tokens: 0 };

function renderPane(profile) {
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

describe("ChatPane — a paused profile is read-only", () => {
  it("hides Edit + Retry when the profile is paused", () => {
    renderPane({ name: "a", model: "x/y", paused: true });
    expect(screen.queryByLabelText("Edit message")).toBeNull();
    expect(screen.queryByLabelText("Retry from here")).toBeNull();
  });

  it("shows Edit + Retry when the profile is active", () => {
    renderPane({ name: "a", model: "x/y" });
    expect(screen.getByLabelText("Edit message")).toBeTruthy();
    expect(screen.getByLabelText("Retry from here")).toBeTruthy();
  });

  it("disables the composer textarea when paused", () => {
    renderPane({ name: "a", model: "x/y", paused: true });
    expect(screen.getByPlaceholderText(/Paused/)).toBeDisabled();
  });

  it("leaves the composer editable when active", () => {
    renderPane({ name: "a", model: "x/y" });
    expect(screen.getByPlaceholderText(/Message a/)).not.toBeDisabled();
  });
});

describe("ChatPane — interleaved reasoning and tools", () => {
  it("renders each reasoning segment before the tool it preceded, in execution order", () => {
    const profile = { name: "a", model: "x/y" };
    const turn = {
      at: 0,
      user: "hi",
      assistant: "answer",
      reasoned_s: 5,
      tools: [
        { name: "search_workspace", reasoning: "let me search", args: { query: "x" }, tool_id: "t1", ok: true, at: 5, duration_s: 1 },
        { name: "read_file", reasoning: "now read the file", args: { path: "p" }, tool_id: "t2", ok: true, at: 8, duration_s: 1 },
      ],
    };
    const { container } = render(
      <ChatPane
        view={{ kind: "profile", profile: profile.name, sessionId: "s1" }}
        profiles={[profile]}
        activeProfile={profile}
        sessionData={{ turns: [turn], last_ctx_tokens: 0 }}
        onSend={vi.fn()}
        onRewriteMessage={vi.fn()}
        onRetryMessage={vi.fn()}
      />,
    );
    const text = container.textContent;
    const order = ["Thought for 5s", "search_workspace", "Thought for 2s", "read_file"].map((s) => text.indexOf(s));
    expect(order.every((v, i) => v >= 0 && (i === 0 || v > order[i - 1]))).toBe(true);
  });

  it("a grouped tool expander exposes aria-expanded and toggles it", () => {
    const profile = { name: "a", model: "x/y" };
    const turn = {
      at: 0,
      user: "hi",
      assistant: "ok",
      tools: [
        { name: "terminal", args: { command: "a" }, tool_id: "t1", ok: true, at: 1, duration_s: 1 },
        { name: "terminal", args: { command: "b" }, tool_id: "t2", ok: true, at: 3, duration_s: 1 },
      ],
    };
    render(
      <ChatPane
        view={{ kind: "profile", profile: profile.name, sessionId: "s1" }}
        profiles={[profile]}
        activeProfile={profile}
        sessionData={{ turns: [turn], last_ctx_tokens: 0 }}
        onSend={vi.fn()}
        onRewriteMessage={vi.fn()}
        onRetryMessage={vi.fn()}
      />,
    );
    const btn = screen.getByLabelText(/Expand 2 terminal calls/);
    expect(btn).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(btn);
    expect(btn).toHaveAttribute("aria-expanded", "true");
  });
});

describe("ChatPane — an interrupted turn is marked, not pending", () => {
  it("shows a discreet interrupted note and no assistant bubble", () => {
    const profile = { name: "a", model: "x/y" };
    const turn = { at: 0, user: "do a long research", assistant: "", tools: [], unfinished: true };
    render(
      <ChatPane
        view={{ kind: "profile", profile: profile.name, sessionId: "s1" }}
        profiles={[profile]}
        activeProfile={profile}
        sessionData={{ turns: [turn], last_ctx_tokens: 0 }}
        onSend={vi.fn()}
        onRewriteMessage={vi.fn()}
        onRetryMessage={vi.fn()}
      />,
    );
    expect(screen.getByText("Interrupted before final reply")).toBeTruthy();
    expect(screen.queryByLabelText("Copy response")).toBeNull();
  });
});
