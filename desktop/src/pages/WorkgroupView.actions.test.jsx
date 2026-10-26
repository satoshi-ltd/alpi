import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn(async () => null) }));
vi.mock("@tauri-apps/api/event", () => ({ listen: vi.fn(async () => () => {}) }));
vi.mock("../lib/workgroup-fetch.js", () => ({
  fetchWorkgroupTranscript: vi.fn(async () => [
    { seq: 1, from_pubkey: "hub-pubkey", body: "first post", at: "2026-10-07T10:00:00Z" },
    { seq: 2, from_pubkey: "hub-pubkey", body: "last post", at: "2026-10-07T10:01:00Z" },
  ]),
}));
vi.mock("../hooks/useProfileDetail.js", () => ({ useProfileDetail: () => ({ detail: null }) }));
vi.mock("../lib/clipboard.js", () => ({ copyText: vi.fn(async () => true) }));

import WorkgroupView from "./WorkgroupView.jsx";
import { copyText } from "../lib/clipboard.js";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };

function mount() {
  return render(
    <WorkgroupView
      workgroup={{ id: "wg", profile: "hub", hub_id: "hub", members: 1 }}
      profiles={[{ name: "hub", accent: "#5588ff", pubkey_b64: "hub-pubkey" }]}
      connectionId="local"
    />,
  );
}

describe("WorkgroupView message actions", () => {
  it("shows the last post's actions at rest and leaves earlier posts on hover and focus", async () => {
    const { container } = mount();
    await waitFor(() => expect(screen.getAllByLabelText("Copy message")).toHaveLength(2));
    const footers = [...container.querySelectorAll(".msg-actions")];
    expect(footers).toHaveLength(2);
    expect(footers[0].hasAttribute("data-rest")).toBe(false);
    expect(footers[1].hasAttribute("data-rest")).toBe(true);
  });

  it("flips the copy label in place instead of raising a toast", async () => {
    mount();
    await waitFor(() => expect(screen.getAllByLabelText("Copy message")).toHaveLength(2));
    await act(async () => { fireEvent.click(screen.getAllByLabelText("Copy message")[1]); });
    expect(copyText).toHaveBeenCalledWith("last post");
    expect(screen.getAllByLabelText("Copied")).toHaveLength(1);
    expect(screen.getAllByLabelText("Copy message")).toHaveLength(1);
  });
});
