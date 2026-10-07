import { act, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const ttsSubs = new Set();

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn(async () => null) }));
vi.mock("@tauri-apps/api/event", () => ({ listen: vi.fn(async () => () => {}) }));
vi.mock("../lib/workgroup-fetch.js", () => ({
  fetchWorkgroupTranscript: vi.fn(async () => [{ seq: 7, from_pubkey: "hub-pubkey", body: "a plain update", at: "2026-10-07T10:00:00Z" }]),
}));
vi.mock("../hooks/useProfileDetail.js", () => ({ useProfileDetail: () => ({ detail: null }) }));
vi.mock("../lib/tts.js", () => ({
  playTts: vi.fn(),
  enqueueTts: vi.fn(),
  clearTtsQueue: vi.fn(),
  voiceForPubkey: () => "voice-a",
  subscribeTts: (fn) => { ttsSubs.add(fn); return () => ttsSubs.delete(fn); },
}));

import WorkgroupView from "./WorkgroupView.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };

describe("WorkgroupView read aloud while preparing", () => {
  it("keeps the verb and shows the control arc, never the word Loading", async () => {
    render(
      <WorkgroupView
        workgroup={{ id: "wg", profile: "hub", hub_id: "hub", members: 1 }}
        profiles={[{ name: "hub", accent: "#5588ff", pubkey_b64: "hub-pubkey" }]}
        connectionId="local"
      />,
    );
    await waitFor(() => expect(screen.getByRole("button", { name: "Read aloud" })).toBeInTheDocument());
    act(() => ttsSubs.forEach((fn) => fn({ key: "wg:wg:7", kind: "loading" })));
    const button = screen.getByRole("button", { name: "Read aloud, preparing audio" });
    expect(button.querySelector("svg.ds-spin")).not.toBeNull();
    expect(document.body.textContent).not.toContain("Loading");
  });
});
