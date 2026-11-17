import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { setSessionTitle } from "../lib/session-titles.js";

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
  const base = { name: "curator", model: "prov/base", shape: "arch", accent: "#f05940" };
  const latest = { id: "s-1", kind: "chat", first_user: "Can we modify a booking\n after an early check-out?", updated_at: Math.floor(Date.now() / 1000) - 8 * 86400 };

  it("introduces the profile with its bio, clamped by the stylesheet, and the full text on hover", () => {
    const bio = "Migration assistant for MINT: inventories legacy bots, jobs and data, classifies reuse/repair/replace/retire, runs parallel comparisons and prepares staff-device authorization handoffs.";
    const { container } = renderEmpty({ ...base, bio: `  ${bio}\n` });
    const line = container.querySelector("p[class*='emptyBio']");
    expect(line.textContent).toBe(bio);
    expect(line.getAttribute("title")).toBe(bio);
    expect(line.className).toMatch(/emptyBio/);
  });

  it("shows no bio line when the profile has none", () => {
    const { container } = renderEmpty({ ...base, bio: "   " });
    expect(container.querySelector("[class*='emptyBio']")).toBeNull();
  });

  it("offers to continue the latest chat session and opens it", () => {
    const onChangeSession = vi.fn();
    renderEmpty({ ...base, latest_session: latest }, { onChangeSession });
    const button = screen.getByRole("button", { name: /Continue “Can we modify a booking after an early check-out\?”/ });
    expect(button.textContent).toContain("1w");
    fireEvent.click(button);
    expect(onChangeSession).toHaveBeenCalledWith("s-1");
  });

  it("titles Continue with the name the user gave the session", () => {
    setSessionTitle(null, "curator", "s-1", "Early check-outs");
    try {
      renderEmpty({ ...base, latest_session: latest }, { onChangeSession: vi.fn() });
      expect(screen.getByRole("button", { name: /Continue “Early check-outs”/ })).toBeInTheDocument();
    } finally {
      setSessionTitle(null, "curator", "s-1", "");
    }
  });

  it("renames Continue as soon as the session is renamed, and names its age apart from the title", () => {
    try {
      renderEmpty({ ...base, latest_session: latest }, { onChangeSession: vi.fn() });
      expect(screen.getByRole("button", { name: "Continue “Can we modify a booking after an early check-out?”, 1w" })).toBeInTheDocument();
      act(() => { setSessionTitle(null, "curator", "s-1", "Early check-outs"); });
      expect(screen.getByRole("button", { name: "Continue “Early check-outs”, 1w" })).toBeInTheDocument();
    } finally {
      setSessionTitle(null, "curator", "s-1", "");
    }
  });

  it("offers no Continue without a chat session to go back to", () => {
    for (const latest_session of [null, { id: "w-1", kind: "workgroup", first_user: "hub post" }, { id: "s-2", kind: "chat", first_user: "  " }]) {
      const { unmount } = renderEmpty({ ...base, latest_session }, { onChangeSession: vi.fn() });
      expect(screen.queryByRole("button", { name: /^Continue/ })).toBeNull();
      unmount();
    }
  });

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
