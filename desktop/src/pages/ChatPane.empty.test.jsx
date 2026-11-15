import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";

import ChatPane from "./ChatPane.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
globalThis.Element.prototype.scrollTo ??= () => {};

beforeEach(() => vi.resetAllMocks());

const hero = (container, shape) => [...container.querySelectorAll(`[data-shape='${shape}']`)].find((el) => el.style.width === "72px");

function renderEmpty(profile, extra = {}) {
  return render(
    <ChatPane
      {...extra}
      view={{ kind: "profile", profile: profile.name, sessionId: null }}
      profiles={[profile]}
      activeProfile={profile}
      sessionData={null}
      onSend={vi.fn()}
      onRewriteMessage={vi.fn()}
      onRetryMessage={vi.fn()}
    />,
  );
}

describe("ChatPane — an empty thread", () => {
  it("shows the profile's own shape at hero size, never Twin", () => {
    const { container } = renderEmpty({ name: "lens", model: "prov/base", shape: "bell", accent: "#3899e2" });
    expect(hero(container, "bell").dataset.mark).toBe("bell");
    expect(screen.getByText("Start a new thread")).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "alpi" })).toBeNull();
  });

  it("draws the default profile as Twin", () => {
    const { container } = renderEmpty({ name: "default", model: "prov/base", shape: "twin", accent: null });
    expect(hero(container, "twin").dataset.mark).toBe("alpi-twin");
  });

  it("draws the profile's shape, not Twin, when it still needs a model", () => {
    const { container } = renderEmpty({ name: "lens", shape: "heart", accent: "#f36a8a", has_any_provider: true });
    expect(screen.getByText("@lens needs a model")).toBeInTheDocument();
    expect(hero(container, "heart")).toBeTruthy();
  });

  it("hands the session state to the header mark, the one animated mark of the chat", () => {
    const header = (container) => container.querySelector(".ds-chat-header [data-shape]");
    const { container, rerender } = renderEmpty({ name: "lens", model: "prov/base", shape: "bell", accent: "#3899e2" }, { markState: "working" });
    expect(header(container).dataset.state).toBe("working");
    const profile = { name: "lens", model: "prov/base", shape: "bell", accent: "#3899e2" };
    rerender(<ChatPane view={{ kind: "profile", profile: "lens", sessionId: null }} profiles={[profile]} activeProfile={profile} sessionData={null} onSend={vi.fn()} markState="failed" />);
    expect(header(container).dataset.state).toBe("failed");
  });

  it("draws the paused state on the hero when the profile is paused, and never follows the pointer", () => {
    const add = vi.spyOn(window, "addEventListener");
    const { container } = renderEmpty({ name: "lens", model: "prov/base", shape: "drop", accent: "#f36a8a", paused: true }, { markState: "paused" });
    const big = hero(container, "drop");
    expect(big.dataset.state).toBe("paused");
    expect(big.querySelector("path[stroke-dasharray]")).not.toBeNull();
    expect(big.querySelector("path[data-body]")).toBeNull();
    expect(big.hasAttribute("data-watch")).toBe(false);
    expect(add.mock.calls.filter(([type]) => type === "mousemove")).toHaveLength(0);
    add.mockRestore();
  });

  it("draws paused on the hero even before the session state catches up", () => {
    const { container } = renderEmpty({ name: "lens", model: "prov/base", shape: "drop", accent: "#f36a8a", paused: true });
    expect(hero(container, "drop").dataset.state).toBe("paused");
  });

  it("draws paused on the needs-a-model hero of a paused profile", () => {
    const { container } = renderEmpty({ name: "lens", shape: "heart", accent: "#f36a8a", has_any_provider: true, paused: true }, { markState: "needs" });
    expect(hero(container, "heart").dataset.state).toBe("paused");
  });

  it("draws the needs-a-model hero in the session state it gets", () => {
    const { container } = renderEmpty({ name: "lens", shape: "heart", accent: "#f36a8a", has_any_provider: true }, { markState: "needs" });
    expect(hero(container, "heart").dataset.state).toBe("needs");
  });

  it("is the only mark that follows the pointer: the hero does, the header does not", () => {
    const { container } = renderEmpty({ name: "lens", model: "prov/base", shape: "bell", accent: "#3899e2" }, { markState: "idle" });
    expect(hero(container, "bell").hasAttribute("data-watch")).toBe(true);
    expect(container.querySelectorAll("[data-watch]")).toHaveLength(1);
    expect(container.querySelector(".ds-chat-header [data-watch]")).toBeNull();
  });

  it("stops the hero following the pointer while the window is unfocused", () => {
    const { container } = renderEmpty({ name: "lens", model: "prov/base", shape: "bell", accent: "#3899e2" }, { markState: "idle" });
    act(() => { window.dispatchEvent(new Event("blur")); });
    expect(container.querySelector("[data-watch], [data-live], animate")).toBeNull();
    expect(hero(container, "bell").dataset.state).toBe("idle");
    act(() => { window.dispatchEvent(new Event("focus")); });
    expect(hero(container, "bell").hasAttribute("data-watch")).toBe(true);
  });
});
