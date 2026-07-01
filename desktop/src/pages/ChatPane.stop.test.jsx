import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import ChatPane from "./ChatPane.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
globalThis.Element.prototype.scrollTo ??= () => {};

function renderPending(onCancel) {
  const profile = { name: "lens", model: "x/y" };
  return render(
    <ChatPane
      view={{ kind: "profile", profile: profile.name, sessionId: "s1" }}
      profiles={[profile]}
      activeProfile={profile}
      sessionData={{ turns: [], last_ctx_tokens: 0 }}
      pendingTurn={{ requestId: "r1", user: "hola", tools: [], at: 0 }}
      onSend={vi.fn()}
      onCancel={onCancel}
      onRewriteMessage={vi.fn()}
      onRetryMessage={vi.fn()}
    />,
  );
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
});
