import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

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
