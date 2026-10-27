import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";

vi.mock("../lib/tts.js", () => ({
  VOICE_POOL: ["voice-default"],
  currentlyPlayingKey: () => null,
  playTts: vi.fn(),
  stopTts: vi.fn(),
  subscribeTts: () => () => {},
  enqueueTts: vi.fn(),
  clearTtsQueue: vi.fn(),
}));

import ChatPane from "./ChatPane.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
globalThis.Element.prototype.scrollTo ??= () => {};

const NOON = new Date(2026, 9, 25, 12).getTime() / 1000;
const CHART = '```chart\n{"type": "bar", "title": "Chats", "x": ["Mon", "Tue"], "series": [{"name": "Chats", "values": [3, 5]}]}\n```';

function renderChat() {
  const profile = { name: "pulse", model: "x/y", accent: "#3fb37a" };
  return render(
    <ChatPane
      view={{ kind: "profile", profile: profile.name, sessionId: "s1" }}
      profiles={[profile]}
      activeProfile={profile}
      connectionId="c1"
      connectionName="casa"
      sessionData={{ turns: [{ user: "report", assistant: `Chats went up.\n\n${CHART}`, at: NOON, ended_at: NOON + 10 }], last_ctx_tokens: 0 }}
      pendingTurn={null}
      onSend={vi.fn()}
      onCancel={vi.fn()}
    />,
  );
}

async function openExport() {
  await act(async () => {});
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "Download" }));
  });
  return screen.getByRole("menu");
}

afterEach(() => {
  document.querySelector(".alpi-print-root")?.remove();
  invoke.mockClear();
});

describe("ChatPane reply exports", () => {
  it("downloads an assistant reply as markdown signed with profile and server", async () => {
    renderChat();
    invoke.mockResolvedValueOnce({ name: "alpi-pulse-a971f9a7-2026-10-25.md" });
    const menu = await openExport();
    await act(async () => {
      fireEvent.click(within(menu).getByRole("menuitem", { name: "Download .md" }));
    });
    expect(invoke).toHaveBeenCalledWith("save_text_file", expect.objectContaining({ name: expect.stringMatching(/^alpi-pulse-[0-9a-f]{8}-2026-10-25\.md$/), dest: "download" }));
    const { content } = invoke.mock.calls.find(([cmd]) => cmd === "save_text_file")[1];
    expect(content).toContain("_@pulse · casa · ");
    expect(content).toContain("```chart");
  });

  it("exports an assistant reply to PDF with its chart and footer", async () => {
    renderChat();
    window.print = vi.fn(async () => {});
    const menu = await openExport();
    await act(async () => {
      fireEvent.click(within(menu).getByRole("menuitem", { name: "Export PDF…" }));
    });
    expect(window.print).toHaveBeenCalledTimes(1);
    const sheet = document.querySelector(".alpi-print-root .alpi-export");
    expect(sheet.textContent).toContain("Chats went up.");
    expect(sheet.querySelector(".ax-chart svg")).not.toBeNull();
    expect(sheet.querySelector(".ax-foot").textContent).toContain("@pulse on casa");
    expect(sheet.querySelector("h1")).toBeNull();
  });
});
