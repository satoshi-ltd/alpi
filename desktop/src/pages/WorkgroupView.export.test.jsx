import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn(async () => ({ name: "ana-2026-10-07.md" })) }));
vi.mock("@tauri-apps/api/event", () => ({ listen: vi.fn(async () => () => {}) }));
vi.mock("../lib/workgroup-fetch.js", () => ({
  fetchWorkgroupTranscript: vi.fn(async () => [{ seq: 7, from_pubkey: "ana-pubkey", body: "Weekly numbers are in.", at: "2026-10-07T10:00:00Z" }]),
}));
vi.mock("../hooks/useProfileDetail.js", () => ({ useProfileDetail: () => ({ detail: null }) }));
vi.mock("../lib/tts.js", () => ({
  playTts: vi.fn(),
  enqueueTts: vi.fn(),
  clearTtsQueue: vi.fn(),
  voiceForPubkey: () => "voice-a",
  subscribeTts: () => () => {},
}));

import { invoke } from "@tauri-apps/api/core";
import WorkgroupView from "./WorkgroupView.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };

function renderGroup() {
  render(
    <WorkgroupView
      workgroup={{ id: "wg", profile: "hub", hub_id: "hub", members: 2 }}
      profiles={[{ name: "hub", pubkey_b64: "hub-pubkey" }, { name: "ana", accent: "#5588ff", pubkey_b64: "ana-pubkey" }]}
      connectionId="c1"
      connectionName="casa"
    />,
  );
}

describe("WorkgroupView post exports", () => {
  it("downloads a post as markdown and exports it to PDF, signed by its author and server", async () => {
    renderGroup();
    await waitFor(() => expect(screen.getByRole("button", { name: "Download" })).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Download" }));
    await act(async () => {
      fireEvent.click(within(screen.getByRole("menu")).getByRole("menuitem", { name: "Download .md" }));
    });
    const { content } = invoke.mock.calls.find(([cmd]) => cmd === "save_text_file")[1];
    expect(content).toContain("Weekly numbers are in.");
    expect(content).toMatch(/_@\S+ · casa · /);

    window.print = vi.fn(async () => {});
    fireEvent.click(screen.getByRole("button", { name: "Download" }));
    await act(async () => {
      fireEvent.click(within(screen.getByRole("menu")).getByRole("menuitem", { name: "Export PDF…" }));
    });
    expect(window.print).toHaveBeenCalledTimes(1);
    const sheet = document.querySelector(".alpi-print-root .alpi-export");
    expect(sheet.textContent).toContain("Weekly numbers are in.");
    expect(sheet.dataset.exportServer).toBe("casa");
    document.querySelector(".alpi-print-root").remove();
  });
});
