import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import ChatPane from "./ChatPane.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
globalThis.Element.prototype.scrollTo ??= () => {};

const TURN = {
  at: 0,
  user: "pick one",
  assistant: "done",
  tools: [{ name: "ask_user", tool_id: "q1", args: { question: "which?" }, output: "the blue one", ok: true }],
};

function answerGlyph(profile) {
  render(
    <ChatPane
      view={{ kind: "profile", profile: profile.name, sessionId: "s1" }}
      profiles={[profile]}
      activeProfile={profile}
      sessionData={{ turns: [TURN], last_ctx_tokens: 0 }}
      onSend={vi.fn()}
      onRewriteMessage={vi.fn()}
      onRetryMessage={vi.fn()}
    />,
  );
  return screen.getByText("the blue one").parentElement.querySelector("[data-shape]");
}

describe("ChatPane — ask_user answer", () => {
  it("marks the answer with the profile's own mark in its colour", () => {
    const glyph = answerGlyph({ name: "doc", model: "x/y", shape: "bell", accent: "#3899e2" });
    expect(glyph.dataset.shape).toBe("bell");
    expect(glyph.dataset.mark).toBe("bell");
    expect(glyph.querySelector("path[data-body]").getAttribute("fill")).toBe("#3899e2");
  });

  it("marks the default profile's answer with Twin", () => {
    expect(answerGlyph({ name: "default", model: "x/y", shape: "twin", accent: null }).dataset.mark).toMatch(/^alpi-twin/);
  });
});
