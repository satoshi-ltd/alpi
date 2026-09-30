import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";

import ChatPane from "./ChatPane.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
globalThis.Element.prototype.scrollTo ??= () => {};

beforeEach(() => {
  vi.resetAllMocks();
  invoke.mockImplementation(async () => null);
});

const profile = { name: "a", model: "prov/sonnet-4" };

function pane(props) {
  return (
    <ChatPane
      view={{ kind: "profile", profile: "a", sessionId: "s1" }}
      profiles={[profile]}
      activeProfile={profile}
      onSend={vi.fn()}
      onRewriteMessage={vi.fn()}
      onRetryMessage={vi.fn()}
      {...props}
    />
  );
}

describe("ChatPane — one footer rule", () => {
  it("keeps the time in the footer and moves usage, model and duration into its tooltip", () => {
    const now = Date.now() / 1000;
    const { container } = render(pane({
      sessionData: {
        model: "prov/sonnet-4",
        turns: [{ user: "hi", assistant: "yo", at: now - 12, ended_at: now, tokens: 3400, cost: 0.0123 }],
      },
    }));
    const tips = [...container.querySelectorAll(".ds-tip-body")].map((n) => n.textContent);
    const meta = tips.find((t) => t.includes("tokens"));
    expect(meta).toContain("3.4K tokens · $0.0123");
    expect(meta).toContain("sonnet-4 · 12s");
    const footers = screen.getAllByText("now");
    expect(footers.length).toBeGreaterThan(0);
    expect(screen.getByLabelText("Copy response").closest("[class*='footActions']")).toBeTruthy();
    expect(screen.getByLabelText("Edit message").closest("[class*='footActions']")).toBeTruthy();
  });
});

describe("ChatPane — only new turns rise in", () => {
  it("leaves the loaded history still and animates a turn appended later", () => {
    const first = { user: "one", assistant: "1", at: 100 };
    const { container, rerender } = render(pane({ sessionData: { turns: [first] } }));
    expect(container.querySelectorAll("[data-enter]")).toHaveLength(0);
    rerender(pane({ sessionData: { turns: [first, { user: "two", assistant: "2", at: 200 }] } }));
    const entering = container.querySelectorAll("[data-enter]");
    expect(entering).toHaveLength(1);
    expect(entering[0].textContent).toContain("two");
  });

  it("does not replay the rise when a streamed turn settles into history", () => {
    const first = { user: "one", assistant: "1", at: 100 };
    const pendingTurn = { requestId: "r1", user: "two", tools: [], assistantPreview: "2", reasoningPreview: "" };
    const { container, rerender } = render(pane({ sessionData: { turns: [first] } }));
    rerender(pane({ sessionData: { turns: [first] }, pendingTurn }));
    expect(container.querySelectorAll("[data-enter]")).toHaveLength(1);
    rerender(pane({ sessionData: { turns: [first, { user: "two", assistant: "2", at: 200 }] }, pendingTurn: { ...pendingTurn, settling: true } }));
    rerender(pane({ sessionData: { turns: [first, { user: "two", assistant: "2", at: 200 }] } }));
    expect(container.querySelectorAll("[data-enter]")).toHaveLength(0);
  });
});

describe("ChatPane — reasoning while streaming", () => {
  const history = { turns: [{ user: "one", assistant: "1", at: 100 }] };

  it("shows the Thinking label with a live peek while the model reasons", () => {
    render(pane({ sessionData: history, pendingTurn: { requestId: "r", user: "q", tools: [], assistantPreview: "", reasoningPreview: "reading the deploy log" } }));
    const row = screen.getByRole("button", { name: "Expand reasoning" });
    expect(row.textContent).toContain("Thinking…");
    expect(row.textContent).toContain("reading the deploy log");
  });

  it("collapses to the Thought row once reasoning_done lands", () => {
    render(pane({ sessionData: history, pendingTurn: { requestId: "r", user: "q", tools: [], assistantPreview: "", reasoningPreview: "plan", reasoned_s: 7, reasoningDone: true } }));
    expect(screen.getByRole("button", { name: "Expand reasoning" }).textContent).toContain("Thought for 7s");
  });
});

describe("ChatPane — approvals ask in the flow", () => {
  it("renders the open chat's approval inside the transcript", () => {
    const { container } = render(pane({
      sessionData: { turns: [{ user: "one", assistant: "1", at: 100 }] },
      inlineApprovals: [{ request_id: "x", profile: "a", command: "rm -rf dist", severity: "caution", session_id: "s1", deadline: null }],
      onApprovalResolved: vi.fn(),
    }));
    const group = screen.getByRole("group", { name: "Allow this command?" });
    expect(within(group).getByText("rm -rf dist")).toBeTruthy();
    expect(within(group).getByRole("button", { name: "Always allow" })).toBeTruthy();
    expect(container.querySelector("[class*='timeline']").contains(group)).toBe(true);
  });
});

describe("ChatPane — an inline request is never stranded", () => {
  const approval = { request_id: "x", profile: "a", command: "make build", severity: "caution", session_id: "s1", deadline: null };

  it("shows it next to a failed transcript load", () => {
    render(pane({ sessionData: null, loadError: "boom", onRetryLoad: vi.fn(), inlineApprovals: [approval] }));
    expect(screen.getByRole("group", { name: "Allow this command?" })).toBeTruthy();
  });

  it("shows it on the empty new-chat hint", () => {
    render(pane({ view: { kind: "profile", profile: "a", sessionId: null }, sessionData: null, inlineApprovals: [approval] }));
    expect(screen.getByRole("group", { name: "Allow this command?" })).toBeTruthy();
  });

  it("shows it on the needs-a-model screen", () => {
    const bare = { name: "a", model: "" };
    render(pane({ profiles: [bare], activeProfile: bare, sessionData: null, inlineApprovals: [approval] }));
    expect(screen.getByRole("group", { name: "Allow this command?" })).toBeTruthy();
  });
});
