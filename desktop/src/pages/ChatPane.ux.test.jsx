import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";

vi.mock("../lib/clipboard.js", () => ({ copyText: vi.fn(async () => true) }));

import ChatPane from "./ChatPane.jsx";
import { NotificationProvider } from "../primitives/Notification.jsx";
import { copyText } from "../lib/clipboard.js";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
globalThis.Element.prototype.scrollTo ??= () => {};

beforeEach(() => {
  vi.useRealTimers();
  invoke.mockImplementation(async () => null);
  copyText.mockClear();
  copyText.mockImplementation(async () => true);
});

const profile = { name: "a", model: "prov/m" };
const turns = [
  { user: "one", assistant: "first", at: 100 },
  { user: "two", assistant: "second", at: 200 },
];

function pane(props = {}) {
  return (
    <ChatPane
      view={{ kind: "profile", profile: "a", sessionId: "s1" }}
      profiles={[profile]}
      activeProfile={profile}
      sessionData={{ turns }}
      onSend={vi.fn()}
      {...props}
    />
  );
}

describe("ChatPane paused", () => {
  it("offers Resume on the banner and beside the composer reason, both running the header action", () => {
    const onTogglePauseProfile = vi.fn();
    render(pane({ activeProfile: { ...profile, paused: true }, onTogglePauseProfile }));
    const buttons = screen.getAllByRole("button", { name: "Resume" });
    expect(buttons).toHaveLength(2);
    fireEvent.click(buttons[0]);
    fireEvent.click(buttons[1]);
    expect(onTogglePauseProfile).toHaveBeenCalledTimes(2);
  });

  it("offers no Resume when the viewer cannot toggle the pause", () => {
    render(pane({ activeProfile: { ...profile, paused: true } }));
    expect(screen.queryByRole("button", { name: "Resume" })).toBeNull();
  });
});

describe("ChatPane copy feedback", () => {
  it("flips the button label in place for 1.5 s instead of raising a toast", async () => {
    vi.useFakeTimers();
    render(pane());
    const buttons = screen.getAllByLabelText("Copy response");
    await act(async () => { fireEvent.click(buttons[0]); });
    expect(copyText).toHaveBeenCalledWith("first");
    expect(screen.getAllByLabelText("Copied")).toHaveLength(1);
    expect(screen.queryByText("Message copied")).toBeNull();
    await act(async () => { vi.advanceTimersByTime(1600); });
    expect(screen.queryByLabelText("Copied")).toBeNull();
    expect(screen.getAllByLabelText("Copy response")).toHaveLength(2);
  });

  it("keeps the label and raises an error toast when the copy fails", async () => {
    copyText.mockImplementation(async () => false);
    render(<NotificationProvider>{pane()}</NotificationProvider>);
    await act(async () => { fireEvent.click(screen.getAllByLabelText("Copy response")[0]); });
    expect(screen.queryByLabelText("Copied")).toBeNull();
    expect(await screen.findByText("Copy failed")).toBeInTheDocument();
  });
});

describe("ChatPane actions at rest", () => {
  it("shows the last turn's actions at rest and leaves earlier turns on hover", () => {
    render(pane());
    const rest = (el) => el.closest("[class*='footActions']").className.includes("footActionsRest");
    const copies = screen.getAllByLabelText("Copy response");
    expect(rest(copies[0])).toBe(false);
    expect(rest(copies[1])).toBe(true);
  });
});
