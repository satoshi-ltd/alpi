import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const tail = vi.hoisted(() => ({ value: null }));
vi.mock("../hooks/useSidecarTail.js", () => ({ useSidecarTail: () => tail.value }));

import ChatPane from "./ChatPane.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
globalThis.Element.prototype.scrollTo ??= () => {};

const profile = { name: "a", model: "x/y" };
const stub = { at: 0, user: "how many force reviews?", assistant: "", tools: [] };

function renderInFlight() {
  return render(
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
}

describe("ChatPane — a turn another window started", () => {
  it("shows the sentence written before a pending tool call as the running step", () => {
    tail.value = { tools: [], assistant: "", note: "Sweeping Bitbucket now", reasoning: "", reasoningDone: false };
    renderInFlight();
    expect(screen.getByRole("button", { name: "Working · Sweeping Bitbucket now" })).toBeInTheDocument();
  });
});
