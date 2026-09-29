import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";

import ChatPane from "./ChatPane.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
globalThis.Element.prototype.scrollTo ??= () => {};

beforeEach(() => {
  vi.resetAllMocks();
  vi.useFakeTimers();
});
afterEach(() => vi.useRealTimers());

const profile = { name: "a", model: "prov/base" };

describe("ChatPane — a conversation that fails to load", () => {
  it("replaces the skeleton with the reason and a Retry", () => {
    const onRetryLoad = vi.fn();
    render(
      <ChatPane
        view={{ kind: "profile", profile: "a", sessionId: "s1" }}
        profiles={[profile]}
        activeProfile={profile}
        sessionData={null}
        loadError="read timeout"
        onRetryLoad={onRetryLoad}
        onSend={vi.fn()}
        onRewriteMessage={vi.fn()}
        onRetryMessage={vi.fn()}
      />,
    );
    act(() => vi.advanceTimersByTime(1000));
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't load this conversation");
    expect(screen.getByText("read timeout")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetryLoad).toHaveBeenCalledTimes(1);
  });
});
