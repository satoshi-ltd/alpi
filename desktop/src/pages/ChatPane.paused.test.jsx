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

describe("ChatPane — consolidated tool module and reasoning", () => {
  it("shows the active tool, buckets the rest, and puts the reasoning chain below", () => {
    const profile = { name: "a", model: "x/y" };
    const turn = {
      at: 0,
      user: "hi",
      assistant: "answer",
      reasoned_s: 5,
      reasoning: "let me search\n\nnow read the file",
      tools: [
        { name: "knowledge", args: { action: "search", query: "x" }, tool_id: "t1", ok: true, at: 5, duration_s: 1 },
        { name: "read_file", args: { path: "p" }, tool_id: "t2", ok: true, at: 8, duration_s: 1 },
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
    expect(text).toContain("2 tool calls");
    const bucketIdx = text.indexOf("2 tool calls");
    const reasoningIdx = text.indexOf("thinking · 5s");
    expect(bucketIdx).toBeGreaterThanOrEqual(0);
    expect(reasoningIdx).toBeGreaterThan(bucketIdx);
  });

  it("a running turn keeps the active call out of the bucket", () => {
    const profile = { name: "a", model: "x/y" };
    const turn = {
      user: "hi",
      tools: [
        { name: "read_file", args: { path: "a" }, tool_id: "t1", ok: true },
        { name: "terminal", args: { command: "b" }, tool_id: "t2", ok: null },
      ],
      reasoningPreview: "",
      pending: true,
    };
    render(
      <ChatPane
        view={{ kind: "profile", profile: profile.name, sessionId: "s1" }}
        profiles={[profile]}
        activeProfile={profile}
        sessionData={{ turns: [turn], last_ctx_tokens: 0, in_flight: true }}
        onSend={vi.fn()}
        onRewriteMessage={vi.fn()}
        onRetryMessage={vi.fn()}
      />,
    );
    expect(screen.getByText("+1 previous tool call")).toBeTruthy();
    expect(screen.getByText("terminal")).toBeTruthy();
  });

  it("the finished-tools bucket exposes aria-expanded and toggles it", () => {
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
    const btn = screen.getByLabelText(/Show 2 tool calls/);
    expect(btn).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(btn);
    expect(btn).toHaveAttribute("aria-expanded", "true");
  });

  it("a single tool shows inline, no bucket", () => {
    const profile = { name: "a", model: "x/y" };
    const turn = {
      at: 0, user: "hi", assistant: "ok",
      tools: [{ name: "read", args: { path: "a" }, tool_id: "t1", ok: true, at: 1, duration_s: 1 }],
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
    expect(screen.getByText("read")).toBeTruthy();
    expect(screen.queryByText(/tool calls?$/)).toBeNull();
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

describe("ChatPane — a still-running turn reads as in progress, not interrupted", () => {
  const profile = { name: "a", model: "x/y" };
  const stub = { at: 0, user: "do a long research", assistant: "", tools: [] };

  it("shows a still-working note when the daemon reports the session in_flight", () => {
    render(
      <ChatPane
        view={{ kind: "profile", profile: profile.name, sessionId: "s1" }}
        profiles={[profile]}
        activeProfile={profile}
        sessionData={{ turns: [stub], last_ctx_tokens: 0, in_flight: true }}
        onSend={vi.fn()}
        onRewriteMessage={vi.fn()}
        onRetryMessage={vi.fn()}
      />,
    );
    expect(screen.getByText("Still working…")).toBeTruthy();
    expect(screen.queryByText("Interrupted before final reply")).toBeNull();
  });

  it("shows nothing for the same stub when the session is not in_flight", () => {
    render(
      <ChatPane
        view={{ kind: "profile", profile: profile.name, sessionId: "s1" }}
        profiles={[profile]}
        activeProfile={profile}
        sessionData={{ turns: [stub], last_ctx_tokens: 0, in_flight: false }}
        onSend={vi.fn()}
        onRewriteMessage={vi.fn()}
        onRetryMessage={vi.fn()}
      />,
    );
    expect(screen.queryByText("Still working…")).toBeNull();
    expect(screen.queryByText("Interrupted before final reply")).toBeNull();
  });

  it("a genuinely interrupted turn still wins over in_flight", () => {
    const interrupted = { ...stub, unfinished: true };
    render(
      <ChatPane
        view={{ kind: "profile", profile: profile.name, sessionId: "s1" }}
        profiles={[profile]}
        activeProfile={profile}
        sessionData={{ turns: [interrupted], last_ctx_tokens: 0, in_flight: true }}
        onSend={vi.fn()}
        onRewriteMessage={vi.fn()}
        onRetryMessage={vi.fn()}
      />,
    );
    expect(screen.getByText("Interrupted before final reply")).toBeTruthy();
    expect(screen.queryByText("Still working…")).toBeNull();
  });
});
