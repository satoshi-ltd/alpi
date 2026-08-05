import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";

import ChatPane from "./ChatPane.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
globalThis.Element.prototype.scrollTo ??= () => {};

beforeEach(() => {
  vi.resetAllMocks();
  invoke.mockImplementation(async () => null);
});

function renderTurn(turn) {
  return render(
    <ChatPane
      view={{ kind: "profile", profile: "a", sessionId: "s1" }}
      profiles={[{ name: "a", model: "prof/ile" }]}
      activeProfile={{ name: "a", model: "prof/ile" }}
      sessionData={{ turns: [turn], model: "prof/ile" }}
      onSend={vi.fn()}
    />,
  );
}

describe("ChatPane — a long turn's reply is stamped when it landed", () => {
  it("stamps the question at turn start and the reply at turn end", () => {
    const now = Date.now() / 1000;
    renderTurn({
      user: "research this",
      assistant: "done",
      at: now - 25 * 60,
      ended_at: now - 5,
    });

    expect(screen.getByText("25m")).toBeTruthy();
    expect(screen.getByText("now")).toBeTruthy();
  });

  it("falls back to turn start for sessions written before the end stamp existed", () => {
    const now = Date.now() / 1000;
    renderTurn({ user: "research this", assistant: "done", at: now - 25 * 60 });

    expect(screen.getAllByText("25m")).toHaveLength(2);
    expect(screen.queryByText("now")).toBeNull();
  });
});
