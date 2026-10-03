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
  return screen.getByText("the blue one").parentElement.querySelector("[data-fold]");
}

describe("ChatPane — ask_user answer", () => {
  it("marks the answer with the profile's own fold in its colour", () => {
    const glyph = answerGlyph({ name: "doc", model: "x/y", fold: "shield", accent: "#3899e2" });
    expect(glyph.dataset.fold).toBe("shield");
    expect(glyph.querySelector("polygon")).toBeTruthy();
    expect(document.querySelector(".ds-diamond")).toBeNull();
  });

  it("marks the default profile's answer with the alpaca", () => {
    expect(answerGlyph({ name: "default", model: "x/y", fold: "alpaca", accent: null }).dataset.fold).toBe("alpaca");
  });
});
