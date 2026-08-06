import { render, screen, waitFor, fireEvent, act } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";

const notify = vi.fn();
vi.mock("../../../primitives/Notification.jsx", () => ({ useNotify: () => notify }));

import { StorageField, _clearStorageCache } from "./maintenance.jsx";
import { formatBytes } from "../util.js";

const withMentions = (...extra) => [
  ...PLAN,
  { key: "mentions", label: "Mentions", desc: "threads", size: 4096, count: 2, action: "unlink", destructive: true, group: "conversations" },
  ...extra,
];

const USAGE = [
  { key: "sessions", label: "sessions", path: "/s", size_bytes: 580_000, file_count: 3 },
  { key: "skills", label: "skills", path: "/sk", size_bytes: 6_000, file_count: 3 },
  { key: "memories", label: "memories", path: "/m", size_bytes: 6_000, file_count: 4 },
  { key: "logs", label: "logs", path: "/l", size_bytes: 2_000, file_count: 4 },
  { key: "audio", label: "audio", path: "/a", size_bytes: 181_000, file_count: 1 },
];
const PLAN = [
  { key: "tts", label: "TTS cache", desc: "mp3s", size: 181_000, count: 1, action: "unlink", destructive: false, group: "caches" },
  { key: "logs", label: "Subsystem logs", desc: "logs", size: 247, count: 1, action: "unlink", destructive: false, group: "logs" },
  { key: "knowledge", label: "Knowledge index bloat", desc: "freelist", size: 1024, count: 1, action: "vacuum", destructive: false, group: "knowledge" },
  { key: "sessions", label: "Old sessions", desc: "transcripts", size: 330_000, count: 16, action: "unlink", destructive: true, group: "conversations" },
];

function mockAll({ plan = PLAN } = {}) {
  invoke.mockImplementation(async (cmd) => {
    if (cmd === "profile_storage") return USAGE;
    if (cmd === "cleanup_plan") return plan;
    if (cmd === "cleanup_apply") return [{ ok: true, removed: 1, freed_bytes: 1000 }];
    return null;
  });
}

const local = { id: "local", kind: "local" };

beforeEach(() => {
  _clearStorageCache();
  invoke.mockReset();
  notify.mockReset();
});

describe("StorageField", () => {
  it("collapses the raw storage keys into concept groups", async () => {
    mockAll();
    render(<StorageField profile={{ name: "doc" }} activeConnection={local} />);
    expect(await screen.findByText("Conversations")).toBeInTheDocument();
    expect(screen.getByText("Skills")).toBeInTheDocument();
    expect(screen.getByText("Memories")).toBeInTheDocument();
    expect(screen.getByText("Logs")).toBeInTheDocument();
    expect(screen.getByText("Caches")).toBeInTheDocument();
    expect(screen.queryByText("Subsystem logs")).toBeNull();
    expect(screen.queryByText("Curator reports")).toBeNull();
  });

  it("offers a single Clean that reclaims every safe key and no destructive one", async () => {
    mockAll();
    render(<StorageField profile={{ name: "doc" }} activeConnection={local} />);
    const btn = await screen.findByRole("button", { name: /^Clean ·/ });
    await act(async () => { fireEvent.click(btn); });
    await waitFor(() =>
      expect(invoke).toHaveBeenCalledWith("cleanup_apply", expect.objectContaining({
        profile: "doc",
        keys: expect.arrayContaining(["tts", "logs", "knowledge"]),
      })),
    );
    const applyCall = invoke.mock.calls.find((c) => c[0] === "cleanup_apply");
    expect(applyCall[1].keys).not.toContain("sessions");
  });

  it("shows destructive cleanup inline with what it removes and confirms", async () => {
    mockAll();
    render(<StorageField profile={{ name: "doc" }} activeConnection={local} />);
    expect(await screen.findByText("chats older than 30 days")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(await screen.findByText("Delete chats older than 30 days?")).toBeInTheDocument();
  });

  it("shows no clean action for content-only groups when nothing is reclaimable", async () => {
    mockAll({ plan: [] });
    render(<StorageField profile={{ name: "doc" }} activeConnection={local} />);
    await screen.findByText("Skills");
    expect(screen.queryByRole("button", { name: /Clean/ })).toBeNull();
    expect(screen.queryByText("Reveal")).toBeNull();
  });

  it("routes storage and cleanup reads to the selected connection", async () => {
    mockAll();
    render(
      <StorageField profile={{ name: "doc" }} activeConnection={{ id: "casa", kind: "remote", role: "admin" }} />,
    );
    await waitFor(() =>
      expect(invoke).toHaveBeenCalledWith("profile_storage", { profile: "doc", connectionId: "casa" }),
    );
    await waitFor(() =>
      expect(invoke).toHaveBeenCalledWith("cleanup_plan", { profile: "doc", connectionId: "casa" }),
    );
  });

  it("cancelling the confirm deletes nothing", async () => {
    mockAll();
    render(<StorageField profile={{ name: "doc" }} activeConnection={local} />);
    fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
    fireEvent.click(await screen.findByRole("button", { name: "Cancel" }));
    expect(invoke.mock.calls.some((c) => c[0] === "cleanup_apply")).toBe(false);
  });

  it("deleting one destructive category applies only its own key", async () => {
    mockAll({ plan: withMentions() });
    render(<StorageField profile={{ name: "doc" }} activeConnection={local} />);
    await screen.findByText("all @-mention threads");
    const rows = screen.getAllByRole("button", { name: "Delete" });
    await act(async () => { fireEvent.click(rows[0]); });
    const confirm = screen.getAllByRole("button", { name: "Delete" }).find((b) => !rows.includes(b));
    await act(async () => { fireEvent.click(confirm); });
    const call = invoke.mock.calls.find((c) => c[0] === "cleanup_apply");
    expect(call[1].keys).toEqual(["sessions"]);
  });

  it("surfaces a partial failure and still refreshes the plan", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "profile_storage") return USAGE;
      if (cmd === "cleanup_plan") return PLAN;
      if (cmd === "cleanup_apply") return [{ ok: false, removed: 0, freed_bytes: 0, errors: ["disk on fire"] }];
      return null;
    });
    render(<StorageField profile={{ name: "doc" }} activeConnection={local} />);
    const btn = await screen.findByRole("button", { name: /^Clean ·/ });
    const before = invoke.mock.calls.filter((c) => c[0] === "cleanup_plan").length;
    await act(async () => { fireEvent.click(btn); });
    expect(notify).toHaveBeenCalledWith(expect.objectContaining({ variant: "error" }));
    await waitFor(() =>
      expect(invoke.mock.calls.filter((c) => c[0] === "cleanup_plan").length).toBe(before + 1),
    );
  });

  it("refreshes the shown size after a successful clean", async () => {
    let storageReads = 0;
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "profile_storage") {
        storageReads += 1;
        return storageReads === 1
          ? USAGE
          : USAGE.map((r) => (r.key === "logs" ? { ...r, size_bytes: 999, file_count: 1 } : r));
      }
      if (cmd === "cleanup_plan") return PLAN;
      if (cmd === "cleanup_apply") return [{ ok: true, removed: 1, freed_bytes: 2000 }];
      return null;
    });
    render(<StorageField profile={{ name: "doc" }} activeConnection={local} />);
    const btn = await screen.findByRole("button", { name: /^Clean ·/ });
    await act(async () => { fireEvent.click(btn); });
    await waitFor(() => expect(screen.getByText(formatBytes(999))).toBeInTheDocument());
  });
});

describe("DeleteProfileAction", () => {
  it("typed confirm calls onDelete with the profile name", async () => {
    const { DeleteProfileAction } = await import("./maintenance.jsx");
    const onDelete = vi.fn();
    render(<DeleteProfileAction profile={{ name: "gus" }} onDelete={onDelete} />);

    fireEvent.click(screen.getByRole("button", { name: "Delete profile" }));
    fireEvent.change(screen.getAllByRole("textbox").at(-1), { target: { value: "gus" } });
    fireEvent.click(screen.getByRole("button", { name: "Delete @gus" }));

    expect(onDelete).toHaveBeenCalledWith("gus");
  });

  it("stays disarmed until the exact profile name is typed", async () => {
    const { DeleteProfileAction } = await import("./maintenance.jsx");
    const onDelete = vi.fn();
    render(<DeleteProfileAction profile={{ name: "gus" }} onDelete={onDelete} />);

    fireEvent.click(screen.getByRole("button", { name: "Delete profile" }));
    fireEvent.change(screen.getAllByRole("textbox").at(-1), { target: { value: "gu" } });
    expect(screen.getByRole("button", { name: "Delete @gus" })).toBeDisabled();
    expect(onDelete).not.toHaveBeenCalled();
  });
});

describe("StorageField — the destructive confirm has a positioned anchor", () => {
  it("keeps the confirm as a sibling of its trigger inside a relative wrapper", async () => {
    mockAll();
    render(<StorageField profile={{ name: "doc" }} activeConnection={local} />);
    const trigger = await screen.findByRole("button", { name: "Delete" });
    fireEvent.click(trigger);

    const confirm = (await screen.findAllByRole("button", { name: "Delete" }))
      .find((b) => b !== trigger);
    const anchor = trigger.parentElement;
    expect(anchor.className).toMatch(/confirmAnchor/);
    expect(anchor.contains(confirm)).toBe(true);
  });
});
