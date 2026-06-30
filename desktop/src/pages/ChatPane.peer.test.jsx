import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import ChatPane from "./ChatPane.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
globalThis.Element.prototype.scrollTo ??= () => {};

function renderWithTurn(turn, profiles) {
  const profile = { name: "lens", model: "x/y" };
  return render(
    <ChatPane
      view={{ kind: "profile", profile: profile.name, sessionId: "s1" }}
      profiles={profiles ?? [profile]}
      activeProfile={profile}
      sessionData={{ turns: [turn], last_ctx_tokens: 0 }}
      onSend={vi.fn()}
      onRewriteMessage={vi.fn()}
      onRetryMessage={vi.fn()}
    />,
  );
}

const PEER_TURN = {
  at: 0,
  user: "@lingua traduce esto",
  assistant: "«Hola, ¿cómo le va?» es la opción canónica.",
  tools: [
    {
      name: "peer",
      args: { peer_id: "lingua", prompt: "traduce esto" },
      tool_id: "p1",
      ok: true,
      at: 1,
      duration_s: 1,
      output: "«Hola, ¿cómo le va?» es la opción canónica.\n\n---\ntokens: in=1 out=2 · cost=$0.0001",
    },
  ],
};

describe("ChatPane — @mention peer reply card", () => {
  it("renders the peer answer as an attributed card, footer stripped", () => {
    renderWithTurn(PEER_TURN);
    expect(screen.getByText("@lingua")).toBeTruthy();
    expect(screen.getByText(/opción canónica/)).toBeTruthy();
    expect(screen.queryByText(/tokens:/)).toBeNull();
  });

  it("keeps the peer tool-call row (the card does not replace it)", () => {
    renderWithTurn(PEER_TURN);
    expect(screen.getByText("peer")).toBeTruthy();
  });

  it("does not duplicate the reply as a separate assistant bubble", () => {
    renderWithTurn(PEER_TURN);
    expect(screen.getAllByText(/opción canónica/)).toHaveLength(1);
  });

  it("tints the card with the mentioned peer's own accent", () => {
    const { container } = renderWithTurn(PEER_TURN, [
      { name: "lens", model: "x/y", accent: "#111111" },
      { name: "lingua", model: "x/y", accent: "#abcdef" },
    ]);
    const card = container.querySelector('[style*="#abcdef"]');
    expect(card).toBeTruthy();
    expect(card.getAttribute("style")).toContain("#abcdef");
  });

  it("falls back to a normal assistant bubble with no peer tool", () => {
    renderWithTurn({ at: 0, user: "hola", assistant: "respuesta normal", tools: [] });
    expect(screen.queryByText("replied")).toBeNull();
    expect(screen.getByText("respuesta normal")).toBeTruthy();
  });
});
