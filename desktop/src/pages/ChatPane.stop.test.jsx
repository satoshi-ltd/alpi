import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import ChatPane from "./ChatPane.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
globalThis.Element.prototype.scrollTo ??= () => {};

function pendingPane(onCancel, pendingExtra = {}) {
  const profile = { name: "lens", model: "x/y" };
  return (
    <ChatPane
      view={{ kind: "profile", profile: profile.name, sessionId: "s1" }}
      profiles={[profile]}
      activeProfile={profile}
      sessionData={{ turns: [], last_ctx_tokens: 0 }}
      pendingTurn={{ requestId: "r1", user: "hola", tools: [], at: 0, ...pendingExtra }}
      onSend={vi.fn()}
      onCancel={onCancel}
      onRewriteMessage={vi.fn()}
      onRetryMessage={vi.fn()}
    />
  );
}

function renderPending(onCancel, pendingExtra = {}) {
  return render(pendingPane(onCancel, pendingExtra));
}

describe("ChatPane — stop button optimistic feedback", () => {
  it("flips to a 'Stopping' state the instant it is pressed, before the daemon confirms", () => {
    const onCancel = vi.fn();
    renderPending(onCancel);

    const stop = screen.getByLabelText("Stop");
    fireEvent.click(stop);

    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText("Stopping")).toBeTruthy();
    expect(screen.queryByLabelText("Stop")).toBeNull();
  });

  it("ignores repeat presses while already stopping", () => {
    const onCancel = vi.fn();
    renderPending(onCancel);

    fireEvent.click(screen.getByLabelText("Stop"));
    fireEvent.click(screen.getByLabelText("Stopping"));

    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("shows Send, not Stop, while a finished turn waits on its transcript", () => {
    renderPending(vi.fn(), { settling: true });

    expect(screen.getByLabelText("Send")).toBeTruthy();
    expect(screen.queryByLabelText("Stop")).toBeNull();
  });

  it("shows Send, not Stop, for a turn that ended in error and stays on screen", () => {
    renderPending(vi.fn(), { error: "upstream 502", ended: true });

    expect(screen.getByLabelText("Send")).toBeTruthy();
    expect(screen.queryByLabelText("Stop")).toBeNull();
  });

  it("leaves the 'Stopping' state once the turn ends, even when the daemon never confirmed", () => {
    const onCancel = vi.fn();
    const { rerender } = renderPending(onCancel);

    fireEvent.click(screen.getByLabelText("Stop"));
    expect(screen.getByLabelText("Stopping")).toBeTruthy();

    rerender(pendingPane(onCancel, { error: "upstream 502", ended: true }));

    expect(screen.getByLabelText("Send")).toBeTruthy();
    expect(screen.queryByLabelText("Stopping")).toBeNull();
  });
});
