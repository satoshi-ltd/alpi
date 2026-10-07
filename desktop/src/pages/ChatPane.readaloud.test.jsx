import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const playTtsMock = vi.fn();
const stopTtsMock = vi.fn();
let currentKey = null;
const ttsSubs = new Set();

vi.mock("../lib/tts.js", () => ({
  VOICE_POOL: ["voice-default"],
  currentlyPlayingKey: () => currentKey,
  playTts: (...args) => playTtsMock(...args),
  stopTts: () => stopTtsMock(),
  subscribeTts: (fn) => { ttsSubs.add(fn); return () => ttsSubs.delete(fn); },
  enqueueTts: vi.fn(),
  clearTtsQueue: vi.fn(),
}));

import ChatPane from "./ChatPane.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
globalThis.Element.prototype.scrollTo ??= () => {};

function chatElement(readAloudTick = 0) {
  const profile = { name: "lens", model: "x/y", voice_id: "voice-a" };
  return (
    <ChatPane
      view={{ kind: "profile", profile: profile.name, sessionId: "s1" }}
      profiles={[profile]}
      activeProfile={profile}
      sessionData={{
        turnsOffset: 4,
        turns: [
          { user: "first", assistant: "older answer", at: 0 },
          { user: "latest", assistant: "latest answer", at: 1 },
        ],
        last_ctx_tokens: 0,
      }}
      pendingTurn={null}
      onSend={vi.fn()}
      onCancel={vi.fn()}
      onRewriteMessage={vi.fn()}
      onRetryMessage={vi.fn()}
      readAloudTick={readAloudTick}
    />
  );
}

beforeEach(() => {
  currentKey = null;
  playTtsMock.mockReset();
  stopTtsMock.mockReset();
});

describe("ChatPane read aloud shortcut", () => {
  it("reads the latest assistant reply when the tick changes", async () => {
    const { rerender } = render(chatElement(0));

    rerender(chatElement(1));
    await act(async () => {});

    expect(playTtsMock).toHaveBeenCalledWith({
      key: "chat:lens:s1:5",
      profile: "lens",
      voice: "voice-a",
      text: "latest answer",
    });
  });

  it("stops audio when any audio is already active", async () => {
    currentKey = "notif:local:lens:n1";
    const { rerender } = render(chatElement(0));

    rerender(chatElement(1));
    await act(async () => {});

    expect(stopTtsMock).toHaveBeenCalledTimes(1);
    expect(playTtsMock).not.toHaveBeenCalled();
  });

  it("does not re-fire when the transcript updates but the tick is unchanged", async () => {
    const { rerender } = render(chatElement(0));
    rerender(chatElement(1));
    await act(async () => {});
    expect(playTtsMock).toHaveBeenCalledTimes(1);

    playTtsMock.mockClear();
    const profile = { name: "lens", model: "x/y", voice_id: "voice-a" };
    rerender(
      <ChatPane
        view={{ kind: "profile", profile: profile.name, sessionId: "s1" }}
        profiles={[profile]}
        activeProfile={profile}
        sessionData={{
          turnsOffset: 4,
          turns: [
            { user: "first", assistant: "older answer", at: 0 },
            { user: "latest", assistant: "streaming token…", at: 1 },
          ],
          last_ctx_tokens: 0,
        }}
        pendingTurn={null}
        onSend={vi.fn()}
        onCancel={vi.fn()}
        onRewriteMessage={vi.fn()}
        onRetryMessage={vi.fn()}
        readAloudTick={1}
      />,
    );
    await act(async () => {});

    expect(playTtsMock).not.toHaveBeenCalled();
    expect(stopTtsMock).not.toHaveBeenCalled();
  });
});

describe("ChatPane read aloud while preparing", () => {
  it("keeps the verb and shows the control arc, never the word Loading", () => {
    render(chatElement(0));
    act(() => ttsSubs.forEach((fn) => fn({ key: "chat:lens:s1:5", kind: "loading" })));
    const button = screen.getByRole("button", { name: "Read aloud, preparing audio" });
    expect(button.querySelector("svg.ds-spin")).not.toBeNull();
    expect(screen.getAllByRole("button", { name: "Read aloud" })).toHaveLength(1);
    expect(document.body.textContent).not.toContain("Loading");
  });
});

describe("ChatPane sync bar", () => {
  it("waits in ink, never in the profile's colour", async () => {
    const profile = { name: "lens", model: "x/y", accent: "#ff3366" };
    render(
      <ChatPane
        view={{ kind: "profile", profile: profile.name, sessionId: "s1" }}
        profiles={[profile]}
        activeProfile={profile}
        sessionData={{ turnsOffset: 0, turns: [], last_ctx_tokens: 0 }}
        sessionSync={{ sessionId: "s1" }}
        pendingTurn={null}
        onSend={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    const bar = await screen.findByRole("progressbar", { name: "syncing conversation" }, { timeout: 2000 });
    expect(bar.getAttribute("style")).toBeNull();
    expect(bar.outerHTML).not.toContain("#ff3366");
  });
});
