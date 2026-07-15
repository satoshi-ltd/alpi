import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const { invokeMock } = vi.hoisted(() => ({ invokeMock: vi.fn(async () => ({})) }));
vi.mock("@tauri-apps/api/core", () => ({ invoke: invokeMock }));

import ChatPane from "./ChatPane.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
globalThis.Element.prototype.scrollTo ??= () => {};

const sessionData = { turns: [{ user: "hi", assistant: "yo", at: 0 }], last_ctx_tokens: 0 };

function renderPane(extra = {}) {
  return render(
    <ChatPane
      view={{ kind: "profile", profile: "a", sessionId: "s1" }}
      profiles={[{ name: "a", model: "x/y" }]}
      activeProfile={{ name: "a", model: "x/y" }}
      sessionData={sessionData}
      onSend={vi.fn()}
      onRewriteMessage={vi.fn()}
      onRetryMessage={vi.fn()}
      {...extra}
    />,
  );
}

beforeEach(() => {
  invokeMock.mockClear();
  try { localStorage.clear(); } catch { /* */ }
});

describe("ChatPane — auto-read toggle by role", () => {
  it("member: toggle is present and flips a client-local pref, never the daemon flag", () => {
    renderPane({ canManageProfileSurfaces: false });
    fireEvent.click(screen.getByLabelText("More"));
    const btn = screen.getByText("Auto-read replies").closest("button");
    expect(btn).toBeTruthy();
    fireEvent.click(btn);
    expect(localStorage.getItem("alpi:autoread:local:a")).toBe("1");
    expect(invokeMock.mock.calls.some((c) => c[0] === "voice_set_auto_read")).toBe(false);
  });

  it("admin: toggle writes the profile-global daemon flag, not localStorage", () => {
    renderPane({ canManageProfileSurfaces: true });
    fireEvent.click(screen.getByLabelText("More"));
    fireEvent.click(screen.getByText("Auto-read replies").closest("button"));
    expect(invokeMock.mock.calls.some((c) => c[0] === "voice_set_auto_read")).toBe(true);
    expect(localStorage.getItem("alpi:autoread:local:a")).toBeNull();
  });
});
