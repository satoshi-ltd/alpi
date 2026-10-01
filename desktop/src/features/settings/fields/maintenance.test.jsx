import { render, screen, waitFor, fireEvent, act, within } from "@testing-library/react";
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

  it("counts run journals inside the Logs group", async () => {
    const usage = [...USAGE, { key: "runs", label: "runs", path: "/r", size_bytes: 6_000_000, file_count: 7 }];
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "profile_storage") return usage;
      if (cmd === "cleanup_plan") return [];
      return null;
    });
    render(<StorageField profile={{ name: "doc" }} activeConnection={local} />);
    expect(await screen.findByText("11 files")).toBeInTheDocument();
    expect(screen.getByText(formatBytes(6_002_000))).toBeInTheDocument();
  });

  it("offers a category that weighs nothing but has items", async () => {
    const usage = [...USAGE, { key: "tombstones", label: "tombstones", path: "/t", size_bytes: 0, file_count: 5 }];
    const plan = [{ key: "tombstones", label: "Workgroup tombstones", desc: "markers", size: 0, count: 5, action: "unlink", destructive: false, group: "caches" }];
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "profile_storage") return usage;
      if (cmd === "cleanup_plan") return plan;
      if (cmd === "cleanup_apply") return [{ ok: true, removed: 5, freed_bytes: 0 }];
      return null;
    });
    render(<StorageField profile={{ name: "doc" }} activeConnection={local} />);
    expect(await screen.findByText("6 files")).toBeInTheDocument();
    const btn = await screen.findByRole("button", { name: "Clean caches · 0 B · 5 items" });
    expect(screen.queryByText(/Clean everything safe/)).toBeNull();
    await act(async () => { fireEvent.click(btn); });
    await waitFor(() =>
      expect(invoke).toHaveBeenCalledWith("cleanup_apply", expect.objectContaining({ keys: ["tombstones"] })),
    );
    await waitFor(() =>
      expect(notify).toHaveBeenCalledWith(expect.objectContaining({ message: "Clean caches: freed 0 B · 5 items", variant: "success" })),
    );
  });

  it("offers one Clean everything safe line that reclaims every safe key and no destructive one", async () => {
    mockAll();
    render(<StorageField profile={{ name: "doc" }} activeConnection={local} />);
    const btn = await screen.findByRole("button", { name: /^Clean everything safe ·/ });
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

  it("cleans only its own group from a group's Clean", async () => {
    mockAll();
    render(<StorageField profile={{ name: "doc" }} activeConnection={local} />);
    const btn = await screen.findByRole("button", { name: /^Clean logs ·/ });
    await act(async () => { fireEvent.click(btn); });
    await waitFor(() =>
      expect(invoke).toHaveBeenCalledWith("cleanup_apply", expect.objectContaining({ keys: ["logs"] })),
    );
  });

  it("shows destructive cleanup inline with what it removes and confirms", async () => {
    mockAll();
    render(<StorageField profile={{ name: "doc" }} activeConnection={local} />);
    fireEvent.click(await screen.findByRole("button", { name: "Delete sessions" }));
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
    fireEvent.click(await screen.findByRole("button", { name: "Delete sessions" }));
    fireEvent.click(await screen.findByRole("button", { name: "Cancel" }));
    expect(invoke.mock.calls.some((c) => c[0] === "cleanup_apply")).toBe(false);
  });

  it("deleting one destructive category applies only its own key", async () => {
    mockAll({ plan: withMentions() });
    render(<StorageField profile={{ name: "doc" }} activeConnection={local} />);
    const trigger = await screen.findByRole("button", { name: "Delete sessions" });
    expect(screen.getByRole("button", { name: "Delete @-mention threads" })).toBeInTheDocument();
    await act(async () => { fireEvent.click(trigger); });
    const confirm = screen.getAllByRole("button", { name: "Delete" }).at(-1);
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
    const btn = await screen.findByRole("button", { name: /^Clean everything safe ·/ });
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
    const btn = await screen.findByRole("button", { name: /^Clean everything safe ·/ });
    await act(async () => { fireEvent.click(btn); });
    await waitFor(() => expect(screen.getByText(formatBytes(999))).toBeInTheDocument());
  });
});

describe("StorageField — one inventory", () => {
  const FULL_USAGE = [
    { key: "sessions", label: "sessions", path: "/s", size_bytes: 6_500_000, file_count: 56 },
    { key: "workgroups", label: "workgroups", path: "/w", size_bytes: 90_000, file_count: 2 },
    { key: "mentions", label: "mentions", path: "/m", size_bytes: 12_000, file_count: 3 },
    { key: "outputs", label: "outputs", path: "/o", size_bytes: 4_500_000, file_count: 12 },
    { key: "generated", label: "generated", path: "/g", size_bytes: 34_000, file_count: 1 },
    { key: "logs", label: "logs", path: "/l", size_bytes: 1_100_000, file_count: 11 },
    { key: "runs", label: "runs", path: "/r", size_bytes: 21_800_000, file_count: 135 },
  ];
  const FULL_PLAN = [
    { key: "sessions", label: "Old sessions", desc: "x", size: 6_400_000, count: 54, action: "unlink", destructive: true, group: "conversations" },
    { key: "workgroups", label: "Workgroup history", desc: "x", size: 90_000, count: 2, action: "unlink", destructive: true, group: "conversations" },
    { key: "mentions", label: "Mentions", desc: "x", size: 12_000, count: 3, action: "unlink", destructive: true, group: "conversations" },
    { key: "generated", label: "Generated files", desc: "x", size: 34_000, count: 1, action: "unlink", destructive: true, group: "files" },
    { key: "attachments", label: "Staged attachments", desc: "x", size: 5_000, count: 2, action: "unlink", destructive: false, group: "files" },
    { key: "runs", label: "Run journals", desc: "x", size: 21_800_000, count: 135, action: "unlink", destructive: true, group: "logs" },
    { key: "logs", label: "Subsystem logs", desc: "x", size: 1_000, count: 3, action: "unlink", destructive: false, group: "logs" },
  ];

  function renderFull(plan = FULL_PLAN, connection = local) {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "profile_storage") return FULL_USAGE;
      if (cmd === "cleanup_plan") return plan;
      return null;
    });
    return render(<StorageField profile={{ name: "doc" }} activeConnection={connection} />);
  }

  it("gives each group its own actions and drops the reclaim and delete rows", async () => {
    renderFull();
    await screen.findByText("Conversations");

    expect(screen.queryByText("reclaim")).toBeNull();
    expect(screen.queryByText("delete")).toBeNull();
    expect(screen.getByRole("button", { name: "Delete sessions" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete workgroup transcripts" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete @-mention threads" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete generated files" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete run journals" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /^Clean (files|logs) ·/ })).toHaveLength(2);
    expect(screen.queryByRole("button", { name: /^Clean conversations/ })).toBeNull();
  });

  it("has one row per non-empty group plus one, with no repeated label", async () => {
    renderFull();
    await screen.findByText("Conversations");
    const labels = ["Conversations", "Files", "Logs", "everything"];
    for (const label of labels) expect(screen.getAllByText(label)).toHaveLength(1);
  });

  it("makes the per-group Clean amounts add up to the sweep total", async () => {
    renderFull();
    await screen.findByText("Conversations");
    const files = FULL_PLAN.filter((m) => m.group === "files" && !m.destructive);
    const logs = FULL_PLAN.filter((m) => m.group === "logs" && !m.destructive);
    const amount = (rows) => `${formatBytes(rows.reduce((n, m) => n + m.size, 0))} · ${rows.reduce((n, m) => n + m.count, 0)} items`;

    expect(screen.getByRole("button", { name: `Clean files · ${amount(files)}` })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: `Clean logs · ${amount(logs)}` })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: `Clean everything safe · ${amount([...files, ...logs])}` })).toBeInTheDocument();
  });

  it("shows the Clean and the named Delete of a mixed group on its own row", async () => {
    renderFull();
    await screen.findByText("Conversations");
    const rowFor = (label) => {
      let node = screen.getByText(label);
      while (node.parentElement && !node.querySelector("button")) node = node.parentElement;
      return node;
    };
    const logs = within(rowFor("Logs"));
    expect(logs.getByRole("button", { name: /^Clean logs/ })).toBeInTheDocument();
    expect(logs.getByRole("button", { name: "Delete run journals" })).toBeInTheDocument();
    const conversations = within(rowFor("Conversations"));
    expect(conversations.getAllByRole("button")).toHaveLength(3);
    expect(conversations.queryByRole("button", { name: /Clean/ })).toBeNull();
  });

  it("has no more rows than non-empty groups plus one when every category is populated", async () => {
    const usage = [
      ...FULL_USAGE,
      { key: "skills", label: "skills", path: "/k", size_bytes: 6_000, file_count: 3 },
      { key: "memories", label: "memories", path: "/me", size_bytes: 6_000, file_count: 4 },
      { key: "knowledge", label: "knowledge", path: "/kn", size_bytes: 4_500_000, file_count: 1 },
      { key: "audio", label: "audio", path: "/a", size_bytes: 181_000, file_count: 1 },
    ];
    const plan = [
      ...FULL_PLAN,
      { key: "tts", label: "TTS cache", desc: "x", size: 181_000, count: 1, action: "unlink", destructive: false, group: "caches" },
      { key: "knowledge", label: "Knowledge index bloat", desc: "x", size: 1024, count: 1, action: "vacuum", destructive: false, group: "knowledge" },
    ];
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "profile_storage") return usage;
      if (cmd === "cleanup_plan") return plan;
      return null;
    });
    render(<StorageField profile={{ name: "doc" }} activeConnection={local} />);
    await screen.findByText("Conversations");

    const labels = ["Conversations", "Skills", "Memories", "Files", "Knowledge", "Caches", "Logs", "everything"];
    for (const label of labels) expect(screen.getAllByText(label)).toHaveLength(1);
    expect(screen.queryByText("reclaim")).toBeNull();
    expect(screen.queryByText("delete")).toBeNull();
  });

  it("keeps the delete confirm on the row that owns it", async () => {
    renderFull();
    fireEvent.click(await screen.findByRole("button", { name: "Delete run journals" }));
    expect(await screen.findByText("Delete run journals?")).toBeInTheDocument();
  });

  it("gives a group the plan names but the field does not know a row of its own", async () => {
    renderFull([{ key: "novel", label: "Novel junk", desc: "x", size: 100, count: 1, action: "unlink", destructive: true, group: "somewhere" }]);
    expect(await screen.findByText("Other")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete novel junk" })).toBeInTheDocument();
    expect(screen.getByText("100 B")).toBeInTheDocument();
    expect(screen.getByText("1 file")).toBeInTheDocument();
  });

  it("shows no actions to a connection that cannot clean", async () => {
    renderFull(FULL_PLAN, { id: "casa", kind: "remote", role: "member" });
    await screen.findByText("Conversations");
    expect(screen.queryByRole("button", { name: /Clean|Delete/ })).toBeNull();
    expect(screen.queryByText("everything")).toBeNull();
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
    const trigger = await screen.findByRole("button", { name: "Delete sessions" });
    fireEvent.click(trigger);

    const confirm = (await screen.findAllByRole("button", { name: "Delete" }))
      .find((b) => b !== trigger);
    const anchor = trigger.parentElement;
    expect(anchor.className).toMatch(/confirmAnchor/);
    expect(anchor.contains(confirm)).toBe(true);
  });

  it("names a failed storage read instead of claiming nothing is stored", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "profile_storage") throw new Error("read timeout");
      if (cmd === "cleanup_plan") return [];
      return null;
    });
    render(<StorageField profile={{ name: "doc" }} activeConnection={local} />);
    await screen.findByRole("alert");
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't load storage");
    expect(screen.queryByText(/Nothing stored yet/)).toBeNull();
  });
});
