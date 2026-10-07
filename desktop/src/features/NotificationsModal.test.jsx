import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, act, waitFor } from "@testing-library/react";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
globalThis.Element.prototype.scrollTo ??= () => {};

const h = vi.hoisted(() => {
  const ROW = {
    id: "n1",
    profile: "alice",
    connectionId: "c1",
    connectionName: "casa",
    accent: "#abc",
    status: "read",
    type: "info",
    created_at: 1_700_000_000,
    body: "Hello **bold** world",
    voice_id: "en-GB-SoniaNeural",
    delivered_to: [],
  };
  // outputs_read (the detail payload) carries no voice_id — only the list rows do.
  const DETAIL = { ...ROW };
  delete DETAIL.voice_id;
  return {
    ROW, DETAIL, detail: DETAIL, rows: [ROW], profileDetail: null, playTts: vi.fn(), ttsCb: { current: null },
    invoke: vi.fn(async () => ({ path: "/tmp/alpi-attach-1/whoop-sync-failed.md", name: "whoop-sync-failed.md", size: 42 })),
    markRead: vi.fn(), markUnread: vi.fn(async () => ({})), notify: vi.fn(),
  };
});

vi.mock("@tauri-apps/api/core", () => ({ invoke: h.invoke }));

vi.mock("../lib/tts.js", () => ({
  playTts: h.playTts,
  subscribeTts: (fn) => { h.ttsCb.current = fn; return () => { h.ttsCb.current = null; }; },
  VOICE_POOL: ["en-US-AriaNeural"],
}));
vi.mock("../lib/useOnline.js", () => ({ useOnline: () => true }));
vi.mock("../lib/clipboard.js", () => ({ copyText: vi.fn(async () => true) }));
vi.mock("../primitives/Notification.jsx", () => ({ useNotify: () => h.notify }));
vi.mock("../hooks/useOutputs.js", () => ({
  useAllOutputs: () => ({ rows: h.rows, refresh: () => {}, loading: h.loading ?? false, unreachable: h.unreachable ?? [] }),
  useOutput: () => ({ row: h.detail, markRead: h.markRead, markUnread: h.markUnread }),
  useDeleteOutput: () => ({ schedule: () => {}, cancel: () => {} }),
  useMarkAllOutputsRead: () => () => {},
  pendingDeleteKeys: () => [],
  rowKey: (r) => `${r.connectionId}:${r.profile}:${r.id}`,
}));
vi.mock("../hooks/useProfileDetail.js", () => ({
  useProfileDetail: () => ({ detail: h.profileDetail, refresh: () => {} }),
}));

import NotificationsModal, { READ_DWELL_MS } from "./NotificationsModal.jsx";
import { headlineParts } from "../lib/notificationHeadline.js";
import { EMPTY } from "../../../common/emptyCopy.mjs";

beforeEach(() => {
  h.playTts.mockClear();
  h.ttsCb.current = null;
  h.rows = [h.ROW];
  h.loading = false;
  h.unreachable = [];
  h.detail = h.DETAIL;
  h.profileDetail = null;
  h.invoke.mockClear();
  h.markRead.mockClear();
  h.notify.mockClear();
  h.markUnread.mockReset();
  h.markUnread.mockResolvedValue({});
});

function menuItem(name) {
  fireEvent.click(screen.getByRole("button", { name: "More" }));
  return screen.getByRole("menuitem", { name });
}

function renderModal(connections = [{ id: "c1", name: "casa" }]) {
  return render(
    <NotificationsModal
      open
      onClose={() => {}}
      connections={connections}
      onSelect={() => {}}
      onOpenChat={() => {}}
    />,
  );
}

describe("NotificationsModal — read aloud + body rendering", () => {
  it("renders the body with inline bold (no full markdown surface)", () => {
    renderModal();
    const article = document.body.querySelector("article");
    expect(article.textContent).toContain("bold");
    expect(article.querySelector("strong")).toBeTruthy();
    expect(document.body.querySelector(".profmsg, .alpi-md")).toBeNull();
  });

  it("renders the body from the list row without waiting for outputs_read", () => {
    h.detail = null;
    renderModal();
    const article = document.body.querySelector("article");
    expect(article.textContent).toContain("bold");
    expect(screen.getByRole("button", { name: "Reply" })).toBeTruthy();
  });

  it("promotes a '**Label:** body' line into an uppercase eyebrow + paragraph", () => {
    h.rows = [{
      id: "n1", profile: "alice", connectionId: "c1", connectionName: "casa",
      accent: "#abc", status: "read", type: "info", created_at: 1_700_000_000,
      body: "**Veredicto:** Día normal en volumen.", delivered_to: [],
    }];
    renderModal();
    const article = document.body.querySelector("article");
    expect(article.textContent).toContain("Veredicto");
    expect(article.textContent).toContain("Día normal en volumen.");
  });

  it("renders a notification title in the list and as a detail heading", () => {
    h.rows = [{
      id: "n1", profile: "alice", connectionId: "c1", connectionName: "casa",
      accent: "#abc", status: "read", type: "info", created_at: 1_700_000_000,
      title: "whoop sync failed", body: "python3 run.py exited with code 1.", delivered_to: [],
    }];
    renderModal();
    expect(document.body.querySelector("article h2")?.textContent).toBe("whoop sync failed");
    const option = screen.getByRole("option");
    expect(option.textContent).toContain("whoop sync failed");
    expect(option.textContent).toContain("python3 run.py exited");
  });

  it("has a read-aloud button that plays the notification body", () => {
    renderModal();
    fireEvent.click(menuItem("Read aloud"));
    expect(h.playTts).toHaveBeenCalledTimes(1);
    expect(h.playTts.mock.calls[0][0].text).toBe(h.ROW.body);
    expect(h.playTts.mock.calls[0][0].key).toBe("notif:c1:alice:n1");
    expect(h.playTts.mock.calls[0][0].voice).toBe("en-GB-SoniaNeural");
  });

  it("switches to a Stop affordance while playing", () => {
    renderModal();
    expect(screen.queryByLabelText("Stop reading")).toBeNull();
    act(() => h.ttsCb.current?.({ key: "notif:c1:alice:n1", kind: "playing" }));
    expect(screen.getByLabelText("Stop reading")).toBeTruthy();
  });

  it("keeps the verb while it prepares the audio, with the control arc as its icon", () => {
    renderModal();
    act(() => h.ttsCb.current?.({ key: "notif:c1:alice:n1", kind: "loading" }));
    const header = screen.getByRole("button", { name: "Read aloud, preparing audio" });
    expect(header.querySelector("svg.ds-spin")).not.toBeNull();
    const item = menuItem("Read aloud, preparing audio");
    expect(item).toHaveTextContent("Read aloud");
    expect(item.querySelector("svg.ds-spin")).not.toBeNull();
    expect(document.body.textContent).not.toContain("Loading");
  });

  it("shows the connection and lowercase profile in the detail header", () => {
    renderModal([{ id: "c1", name: "casa" }, { id: "c2", name: "work" }]);
    const article = document.body.querySelector("article");
    expect(article.textContent).toContain("@alice");
    expect(article.textContent).toContain("casa");
    expect(article.textContent).not.toContain("@ALICE");
    expect(article.textContent).not.toContain("CASA");
  });

  it("shows a severity chip in the detail header for warnings", () => {
    h.rows = [{ ...h.ROW, type: "warning" }];
    h.detail = { ...h.DETAIL, type: "warning" };
    renderModal();
    expect(document.body.querySelector("article").textContent).toContain("warning");
  });

  it("names a warning or error row's severity with a word, not a dot", () => {
    h.rows = [{ ...h.ROW, type: "warning" }];
    renderModal();
    expect(screen.getByRole("option").querySelector('[class*="rowSev"]').textContent).toBe("warning");
  });

  it("leaves info rows without a severity tag", () => {
    renderModal();
    expect(document.body.querySelector('[class*="rowSev"]')).toBeNull();
  });

  it("groups the list by date", () => {
    renderModal();
    expect(screen.getByText("Earlier")).toBeTruthy();
  });

  it("reads each connection's notification in that profile's configured voice", () => {
    const base = {
      id: "n1", profile: "alice", accent: "#abc",
      status: "read", type: "info", created_at: 1_700_000_000, body: "x", delivered_to: [],
    };
    h.rows = [
      { ...base, connectionId: "c1", connectionName: "casa", voice_id: "en-GB-SoniaNeural" },
      { ...base, connectionId: "c2", connectionName: "work", voice_id: "fr-FR-DeniseNeural" },
    ];
    renderModal([{ id: "c1", name: "casa" }, { id: "c2", name: "work" }]);

    fireEvent.click(menuItem("Read aloud"));
    expect(h.playTts.mock.calls.at(-1)[0]).toMatchObject({
      voice: "en-GB-SoniaNeural", key: "notif:c1:alice:n1",
    });

    fireEvent.click(screen.getAllByRole("option")[1]);
    fireEvent.click(menuItem("Read aloud"));
    expect(h.playTts.mock.calls.at(-1)[0]).toMatchObject({
      voice: "fr-FR-DeniseNeural", key: "notif:c2:alice:n1",
    });
  });

  it("uses the remote profile_detail voice when summaries omits voice_id", () => {
    h.rows = [{ ...h.ROW, voice_id: undefined }];
    h.profileDetail = { voice_id: "es-ES-AlvaroNeural" };
    renderModal();
    fireEvent.click(menuItem("Read aloud"));
    expect(h.playTts.mock.calls.at(-1)[0].voice).toBe("es-ES-AlvaroNeural");
  });

  it("resolves the voice from a sibling row when the active row is absent", () => {
    h.rows = [{
      id: "n9", profile: "alice", connectionId: "c1", connectionName: "casa",
      accent: "#abc", status: "read", type: "info", created_at: 1_700_000_000,
      body: "x", voice_id: "en-GB-SoniaNeural", delivered_to: [],
    }];
    render(
      <NotificationsModal
        open
        onClose={() => {}}
        connections={[{ id: "c1", name: "casa" }]}
        selectedId="n1"
        selectedProfile="alice"
        selectedConnectionId="c1"
        onSelect={() => {}}
        onOpenChat={() => {}}
      />,
    );
    fireEvent.click(menuItem("Read aloud"));
    expect(h.playTts.mock.calls.at(-1)[0].voice).toBe("en-GB-SoniaNeural");
  });
});

describe("headlineParts", () => {
  it("uses the explicit title and a body preview", () => {
    expect(headlineParts({ title: "Sync failed", body: "python3 run.py exited." }))
      .toEqual({ title: "Sync failed", preview: "python3 run.py exited." });
  });

  it("derives the first sentence as the headline when there is no title", () => {
    expect(headlineParts({ body: "Recovery is low. HRV down 8ms vs baseline." }))
      .toEqual({ title: "Recovery is low.", preview: "HRV down 8ms vs baseline." });
  });

  it("uses the whole body as the headline when there is no sentence break", () => {
    expect(headlineParts({ body: "just a short note" }))
      .toEqual({ title: "just a short note", preview: "" });
  });

  it("strips emojis from the headline", () => {
    expect(headlineParts({ title: "🔥 PR #482 ready ✅" }).title).toBe("PR #482 ready");
    expect(headlineParts({ body: "⚠️ Recovery is low. HRV down 8ms." }).title).toBe("Recovery is low.");
  });

  it("strips emojis from the preview too", () => {
    expect(headlineParts({ title: "Recovery", body: "🔴 25% de recovery." }).preview).toBe("25% de recovery.");
  });
});

describe("NotificationsModal — reply + download", () => {
  const TITLED = {
    id: "n1", profile: "alice", connectionId: "c1", connectionName: "casa",
    accent: "#abc", status: "read", type: "error", created_at: 1_700_000_000,
    title: "whoop sync failed", body: "python3 run.py exited with code 1.", delivered_to: [],
  };

  function renderTitled(props = {}) {
    h.rows = [TITLED];
    h.detail = TITLED;
    return render(
      <NotificationsModal
        open
        onClose={() => {}}
        connections={[{ id: "c1", name: "casa" }]}
        onSelect={() => {}}
        onOpenChat={() => {}}
        onSendToChat={() => {}}
        {...props}
      />,
    );
  }

  it("Reply materializes a temp .md and hands the profile a new session with it attached", async () => {
    const onSendToChat = vi.fn();
    renderTitled({ onSendToChat });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Reply" }));
    });
    expect(h.invoke).toHaveBeenCalledWith(
      "save_text_file",
      expect.objectContaining({ name: "whoop-sync-failed.md", dest: "temp" }),
    );
    const { content } = h.invoke.mock.calls[0][1];
    expect(content).toContain("# whoop sync failed");
    expect(content).toContain("@alice");
    expect(content).toContain("python3 run.py exited with code 1.");
    expect(onSendToChat).toHaveBeenCalledWith(
      "alice",
      "c1",
      expect.objectContaining({ name: "whoop-sync-failed.md", mime: "text/markdown", path: expect.any(String) }),
    );
  });

  it("download writes the markdown to the Downloads folder", async () => {
    renderTitled();
    const item = menuItem("Download .md");
    await act(async () => {
      fireEvent.click(item);
    });
    expect(h.invoke).toHaveBeenCalledWith(
      "save_text_file",
      expect.objectContaining({ name: "whoop-sync-failed.md", dest: "download" }),
    );
  });

  it("slugifies an accented, punctuated title into a clean filename", async () => {
    h.rows = [{ ...TITLED, title: "Lobby · insights del día" }];
    h.detail = { ...TITLED, title: "Lobby · insights del día" };
    render(
      <NotificationsModal open onClose={() => {}} connections={[{ id: "c1", name: "casa" }]}
        onSelect={() => {}} onOpenChat={() => {}} onSendToChat={() => {}} />,
    );
    const item = menuItem("Download .md");
    await act(async () => {
      fireEvent.click(item);
    });
    expect(h.invoke.mock.calls[0][1].name).toBe("lobby-insights-del-dia.md");
  });
});

describe("NotificationsModal — read / unread", () => {
  it("header shows the count of unread items", () => {
    h.rows = [
      { ...h.ROW, id: "a", status: "unread" },
      { ...h.ROW, id: "b", status: "unread" },
      { ...h.ROW, id: "c", status: "read" },
    ];
    renderModal();
    expect(document.body.textContent).toContain("2 unread");
  });

  it("marks unread with an ink dot and leaves the profile's object whole, the alpaca included", () => {
    h.rows = [
      { ...h.ROW, id: "a", status: "unread", accent: "#3899e2" },
      { ...h.ROW, id: "b", status: "read", accent: "#3899e2" },
      { ...h.ROW, id: "c", profile: "default", status: "read", accent: null, fold: "alpaca" },
    ];
    renderModal();
    const [unread, read, alpaca] = screen.getAllByRole("option");
    expect(unread.querySelector('[aria-label="Unread"]')).toBeTruthy();
    expect(read.querySelector('[aria-label="Unread"]')).toBeNull();
    expect(read.querySelector("[data-fold]").style.getPropertyValue("--c")).toBe("#3899e2");
    expect(alpaca.querySelector("[data-fold]").dataset.fold).toBe("alpaca");
  });

  it("omits the unread suffix when nothing is unread", () => {
    h.rows = [{ ...h.ROW, id: "a", status: "read" }];
    renderModal();
    expect(document.body.textContent).not.toMatch(/\d+ unread/);
  });

  it("marks an opened row read once it has been open for a moment, without waiting on the daemon", async () => {
    h.rows = [
      { ...h.ROW, id: "a", status: "unread" },
      { ...h.ROW, id: "b", status: "unread" },
    ];
    renderModal();
    expect(document.body.textContent).toContain("2 unread");
    await act(async () => {
      fireEvent.click(screen.getAllByRole("option")[0]);
    });
    expect(document.body.textContent).toContain("2 unread");
    await waitFor(() => expect(document.body.textContent).toContain("1 unread"));
    expect(h.markRead).toHaveBeenCalledTimes(1);
  });

  it("does not mark a row read while the arrows only pass over it", async () => {
    h.rows = [
      { ...h.ROW, id: "a", status: "unread" },
      { ...h.ROW, id: "b", status: "unread", created_at: h.ROW.created_at - 60 },
    ];
    renderModal();
    screen.getByLabelText("Search notifications").focus();
    fireEvent.keyDown(document.activeElement, { key: "ArrowDown" });
    fireEvent.keyDown(document.activeElement, { key: "ArrowDown" });
    await new Promise((resolve) => setTimeout(resolve, READ_DWELL_MS / 2));
    expect(document.body.textContent).toContain("2 unread");
    await waitFor(() => expect(document.body.textContent).toContain("1 unread"));
    expect(screen.getAllByRole("option")[1].getAttribute("aria-selected")).toBe("true");
  });

  it("a deeplink-selected unread row is marked read optimistically without a click", () => {
    h.rows = [
      { ...h.ROW, id: "a", status: "unread" },
      { ...h.ROW, id: "b", status: "unread" },
    ];
    render(
      <NotificationsModal
        open
        onClose={() => {}}
        connections={[{ id: "c1", name: "casa" }]}
        selectedId="a"
        selectedProfile="alice"
        selectedConnectionId="c1"
        onSelect={() => {}}
        onOpenChat={() => {}}
      />,
    );
    return waitFor(() => expect(document.body.textContent).toContain("1 unread"));
  });

  it("deleting an unread row drops the count while it is hidden in the undo window", async () => {
    h.rows = [
      { ...h.ROW, id: "a", status: "unread" },
      { ...h.ROW, id: "b", status: "unread" },
    ];
    renderModal();
    expect(document.body.textContent).toContain("2 unread");
    await act(async () => {
      fireEvent.click(screen.getAllByLabelText("Delete notification")[0]);
    });
    expect(document.body.textContent).toContain("1 unread");
  });

  it("does not claim inbox zero while the first sync is still running", async () => {
    h.rows = [];
    h.loading = true;
    renderModal();
    expect(screen.queryByText("Inbox zero")).toBeNull();
    expect(screen.getByRole("progressbar", { name: "Syncing notifications" })).toBeInTheDocument();
    await waitFor(() => expect(document.querySelectorAll("[role=listbox] li[role=presentation] [class*=listRow]").length).toBeGreaterThan(1));
    expect(screen.queryByText(/Syncing notifications…|Loading/)).toBeNull();
  });
});


describe("NotificationsModal unreachable daemons", () => {
  const renderInbox = () => render(<NotificationsModal open connections={[{ id: "c1", name: "casa" }, { id: "c2", name: "mirai" }]} onClose={() => {}} />);

  it("names the daemons that did not answer above a partial list", () => {
    h.unreachable = ["mirai"];
    renderInbox();
    expect(screen.getByText(/Couldn't reach mirai\. Their notifications are missing/)).toBeInTheDocument();
  });

  it("never claims inbox zero when a daemon did not answer", () => {
    h.rows = [];
    h.unreachable = ["casa", "mirai"];
    renderInbox();
    expect(screen.getByText("Couldn't reach casa, mirai")).toBeInTheDocument();
    expect(screen.queryByText("Inbox zero")).toBeNull();
  });
});

describe("NotificationsModal keyboard", () => {
  it("moves through the rows with the arrow keys and opens the focused one with Enter", () => {
    const second = { ...h.ROW, id: "n2", body: "Second one", created_at: h.ROW.created_at - 60 };
    h.rows = [h.ROW, second];
    const onSelect = vi.fn();
    render(<NotificationsModal open onClose={() => {}} connections={[{ id: "c1", name: "casa" }]} onSelect={onSelect} onOpenChat={() => {}} />);
    const [first, next] = screen.getAllByRole("option");
    screen.getByLabelText("Search notifications").focus();
    fireEvent.keyDown(document.activeElement, { key: "ArrowDown" });
    expect(document.activeElement).toBe(first);
    fireEvent.keyDown(document.activeElement, { key: "ArrowDown" });
    expect(document.activeElement).toBe(next);
    fireEvent.keyDown(document.activeElement, { key: "ArrowUp" });
    expect(document.activeElement).toBe(first);
    fireEvent.keyDown(document.activeElement, { key: "ArrowDown" });
    fireEvent.keyDown(document.activeElement, { key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: "n2" }));
    expect(next.getAttribute("aria-selected")).toBe("true");
  });

  it("opens a row with Space but not when the key lands on its delete button, and moves on from that button", () => {
    const second = { ...h.ROW, id: "n2", body: "Second one", created_at: h.ROW.created_at - 60 };
    h.rows = [h.ROW, second];
    const onSelect = vi.fn();
    render(<NotificationsModal open onClose={() => {}} connections={[{ id: "c1", name: "casa" }]} onSelect={onSelect} onOpenChat={() => {}} />);
    const [first, next] = screen.getAllByRole("option");
    const remove = first.querySelector('[aria-label="Delete notification"]');
    remove.focus();
    fireEvent.keyDown(remove, { key: "Enter" });
    fireEvent.keyDown(remove, { key: " " });
    expect(onSelect).not.toHaveBeenCalled();
    fireEvent.keyDown(remove, { key: "ArrowDown" });
    expect(document.activeElement).toBe(next);
    fireEvent.keyDown(next, { key: " " });
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: "n2" }));
  });

  it("picks the list up again with the arrows after focus fell back to the page", () => {
    h.rows = [h.ROW];
    render(<NotificationsModal open onClose={() => {}} connections={[{ id: "c1", name: "casa" }]} onSelect={() => {}} onOpenChat={() => {}} />);
    document.activeElement.blur();
    fireEvent.keyDown(document.body, { key: "ArrowDown" });
    expect(document.activeElement).toBe(screen.getByRole("option"));
  });
});

describe("NotificationsModal error card", () => {
  const FAILED = {
    ...h.ROW, id: "f1", type: "error", status: "read", title: "Daily mail digest failed", job_id: "j-mail",
    body: "**Reason:** The mail account refused the saved token.\n**Exit:** 1\n\n```text\nTraceback (most recent call last)\n```",
  };

  function renderFailure(props = {}) {
    h.rows = [FAILED];
    h.detail = FAILED;
    return render(<NotificationsModal open onClose={() => {}} connections={[{ id: "c1", name: "casa" }]} activeConnectionId="c1" onSelect={() => {}} onOpenChat={() => {}} {...props} />);
  }

  it("draws a failure as a card: red on the mark and the word failed, facts, the trace folded under Details", () => {
    renderFailure();
    const card = document.body.querySelector("section[aria-label='Daily mail digest failed']");
    expect(card.querySelector("h2").textContent).toBe("Daily mail digest failed");
    expect(card.querySelector("h2 span span").textContent).toBe("failed");
    expect([...card.querySelectorAll("dt")].map((d) => d.textContent)).toEqual(["Reason", "Exit"]);
    expect(card.querySelector("details").open).toBe(false);
    expect(card.querySelector("details summary").textContent).toBe("Details");
    expect(card.querySelector("details pre").textContent).toContain("Traceback");
    expect(document.body.querySelector("article").textContent).not.toContain("error");
  });

  it("runs the job again and opens it from the card", async () => {
    const onOpenJob = vi.fn();
    renderFailure({ onOpenJob });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Run again" })); });
    expect(h.invoke).toHaveBeenCalledWith("schedule_fire", { profile: "alice", connectionId: "c1", id: "j-mail" });
    fireEvent.click(screen.getByRole("button", { name: "Open job" }));
    expect(onOpenJob).toHaveBeenCalledWith("alice", "j-mail");
  });

  it("runs the job once however often Run again is clicked while it starts", async () => {
    let release;
    h.invoke.mockImplementationOnce(() => new Promise((resolve) => { release = resolve; }));
    renderFailure();
    const button = screen.getByRole("button", { name: "Run again" });
    await act(async () => { fireEvent.click(button); fireEvent.click(button); });
    expect(h.invoke.mock.calls.filter(([cmd]) => cmd === "schedule_fire")).toHaveLength(1);
    await act(async () => { release({}); });
  });

  it("titles a failure with no title of its own", () => {
    const untitled = { ...FAILED, title: "" };
    h.rows = [untitled];
    h.detail = untitled;
    render(<NotificationsModal open onClose={() => {}} connections={[{ id: "c1", name: "casa" }]} activeConnectionId="c1" onSelect={() => {}} onOpenChat={() => {}} />);
    expect(document.body.querySelector("section h2").textContent).toBe("Failed");
  });

  it("offers no Open job for a failure on another daemon, and no job actions when it names no job", () => {
    const first = renderFailure({ onOpenJob: vi.fn(), activeConnectionId: "c2" });
    expect(screen.getByRole("button", { name: "Run again" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Open job" })).toBeNull();
    first.unmount();
    const orphan = { ...FAILED, job_id: undefined };
    h.rows = [orphan];
    h.detail = orphan;
    render(<NotificationsModal open onClose={() => {}} connections={[{ id: "c1", name: "casa" }]} activeConnectionId="c1" onSelect={() => {}} onOpenChat={() => {}} onOpenJob={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Run again" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Open job" })).toBeNull();
  });
});

describe("NotificationsModal triage", () => {
  const T = h.ROW.created_at;
  const ROWS = () => [
    { ...h.ROW, id: "e1", status: "unread", type: "error", title: "Backup failed", created_at: T },
    { ...h.ROW, id: "i1", status: "unread", type: "info", title: "Digest", created_at: T - 10 },
    { ...h.ROW, id: "w1", status: "read", type: "warning", title: "Key expiring", created_at: T - 20 },
    { ...h.ROW, id: "b1", profile: "bob", connectionId: "c1", status: "read", type: "info", title: "Bob note", created_at: T - 30 },
  ];
  const titles = () => screen.getAllByRole("option").map((o) => o.querySelector('[class*="rowTitle"]').textContent);
  const renderTriage = (props = {}) => {
    h.rows = ROWS();
    return render(<NotificationsModal open onClose={() => {}} connections={[{ id: "c1", name: "casa" }]} activeConnectionId="c1" onSelect={() => {}} onOpenChat={() => {}} {...props} />);
  };

  it("pins unread errors and warnings in a Needs you group above the days", () => {
    renderTriage();
    expect(screen.getByText("Needs you · 1")).toBeTruthy();
    expect(titles()[0]).toBe("Backup failed");
  });

  it("filters to All, Needs you or Unread with counts, by click or by 1–3 from the list", () => {
    renderTriage();
    expect(screen.getByRole("button", { name: "All4" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Needs you1" }));
    expect(titles()).toEqual(["Backup failed"]);
    fireEvent.keyDown(screen.getByRole("listbox"), { key: "3" });
    expect(titles()).toEqual(["Backup failed", "Digest"]);
    fireEvent.keyDown(screen.getByRole("listbox"), { key: "1" });
    expect(titles()).toHaveLength(4);
  });

  it("draws no per-profile tags or counts above the list", () => {
    renderTriage();
    expect(screen.queryByRole("group", { name: "Profiles" })).toBeNull();
    expect(screen.queryByRole("button", { name: /@bob/ })).toBeNull();
  });

  it("replies with R, deletes with Backspace and moves to the next row, and searches with /", async () => {
    const onSendToChat = vi.fn();
    renderTriage({ onSendToChat });
    const [first, second] = screen.getAllByRole("option");
    fireEvent.click(first);
    await act(async () => { fireEvent.keyDown(first, { key: "r" }); });
    expect(onSendToChat).toHaveBeenCalledWith("alice", "c1", expect.objectContaining({ mime: "text/markdown" }));
    fireEvent.keyDown(first, { key: "Backspace" });
    expect(titles()).not.toContain("Backup failed");
    expect(second.getAttribute("aria-selected")).toBe("true");
    fireEvent.keyDown(screen.getByRole("listbox"), { key: "/" });
    expect(document.activeElement).toBe(screen.getByLabelText("Search notifications"));
  });

  it("marks a read row unread with U and keeps it unread while it stays open", async () => {
    renderTriage();
    const warning = screen.getAllByRole("option").find((o) => o.textContent.includes("Key expiring"));
    fireEvent.click(warning);
    await act(async () => { fireEvent.keyDown(warning, { key: "u" }); });
    expect(h.markUnread).toHaveBeenCalledTimes(1);
    expect(warning.querySelector('[aria-label="Unread"]')).toBeTruthy();
    expect(document.body.textContent).toContain("3 unread");
    await new Promise((resolve) => setTimeout(resolve, READ_DWELL_MS + 100));
    expect(h.markRead).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Mark unread" })).toBeNull();
  });

  it("hides Mark unread once the daemon does not know the verb", async () => {
    h.markUnread.mockRejectedValue(new Error("host.outputs.mark_unread: -32601 method-not-found"));
    renderTriage();
    fireEvent.click(screen.getAllByRole("option").find((o) => o.textContent.includes("Bob note")));
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Mark unread" })); });
    expect(screen.queryByRole("button", { name: "Mark unread" })).toBeNull();
  });

  const dwell = () => new Promise((resolve) => setTimeout(resolve, READ_DWELL_MS + 100));
  const option = (title) => screen.getAllByRole("option").find((o) => o.textContent.includes(title));

  it("opens on the first row of the list and marks it read once the arrows land on it", async () => {
    renderTriage();
    expect(option("Backup failed").getAttribute("aria-selected")).toBe("true");
    screen.getByLabelText("Search notifications").focus();
    fireEvent.keyDown(document.activeElement, { key: "ArrowDown" });
    await dwell();
    expect(h.markRead).toHaveBeenCalledTimes(1);
  });

  it("keeps focus, group and filter on the row being read until the selection moves", async () => {
    renderTriage();
    fireEvent.keyDown(screen.getByRole("listbox"), { key: "2" });
    const row = option("Backup failed");
    row.focus();
    await dwell();
    expect(h.markRead).toHaveBeenCalledTimes(1);
    expect(document.activeElement).toBe(row);
    expect(row.isConnected).toBe(true);
    expect(screen.getByText("Needs you · 1")).toBeTruthy();
    fireEvent.keyDown(row, { key: "r" });
    expect(document.activeElement).toBe(row);
  });

  it("leaves a row unread when the selection moves on within the moment", async () => {
    renderTriage();
    fireEvent.click(option("Digest"));
    fireEvent.click(option("Key expiring"));
    await dwell();
    expect(option("Digest").querySelector('[aria-label="Unread"]')).toBeTruthy();
    expect(h.markRead).not.toHaveBeenCalled();
  });

  it("holds an unread row unread with U without asking the daemon", async () => {
    renderTriage();
    const digest = option("Digest");
    fireEvent.click(digest);
    fireEvent.keyDown(digest, { key: "u" });
    await dwell();
    expect(h.markRead).not.toHaveBeenCalled();
    expect(h.markUnread).not.toHaveBeenCalled();
    expect(digest.querySelector('[aria-label="Unread"]')).toBeTruthy();
  });

  it("gives every Backspace delete its own Undo and ignores a held key", async () => {
    renderTriage();
    const first = option("Backup failed");
    fireEvent.click(first);
    fireEvent.keyDown(first, { key: "Backspace" });
    fireEvent.keyDown(first, { key: "Backspace", repeat: true });
    const next = option("Digest");
    fireEvent.keyDown(next, { key: "Backspace" });
    const undos = h.notify.mock.calls.filter(([arg]) => arg.action === "Undo");
    expect(undos).toHaveLength(2);
    expect(undos.map(([arg]) => arg.message)).toEqual(["Deleted “Backup failed”", "Deleted “Digest”"]);
  });

  it("ignores Backspace pressed on another row's delete button", () => {
    renderTriage();
    fireEvent.click(option("Backup failed"));
    const remove = option("Digest").querySelector('[aria-label="Delete notification"]');
    remove.focus();
    fireEvent.keyDown(remove, { key: "Backspace" });
    expect(h.notify).not.toHaveBeenCalled();
    expect(titles()).toHaveLength(4);
  });

  it("marks a row read when it is acted on before the moment passes", async () => {
    renderTriage({ onSendToChat: vi.fn() });
    fireEvent.click(option("Digest"));
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Reply" })); });
    expect(h.markRead).toHaveBeenCalledTimes(1);
  });

  it("hides Mark unread only for the daemon that does not know the verb", async () => {
    h.markUnread.mockRejectedValue(new Error("-32601 method-not-found"));
    h.rows = [
      { ...h.ROW, id: "a", connectionId: "c1", connectionName: "casa", status: "read", title: "On casa" },
      { ...h.ROW, id: "b", connectionId: "c2", connectionName: "work", status: "read", title: "On work", created_at: h.ROW.created_at - 5 },
    ];
    render(<NotificationsModal open onClose={() => {}} connections={[{ id: "c1", name: "casa" }, { id: "c2", name: "work" }]} onSelect={() => {}} onOpenChat={() => {}} />);
    fireEvent.click(option("On casa"));
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Mark unread" })); });
    expect(screen.queryByRole("button", { name: "Mark unread" })).toBeNull();
    fireEvent.click(option("On work"));
    expect(screen.getByRole("button", { name: "Mark unread" })).toBeTruthy();
  });

  it("keeps a selected read row out of the filters it never matched", () => {
    renderTriage();
    fireEvent.click(option("Bob note"));
    fireEvent.keyDown(screen.getByRole("listbox"), { key: "2" });
    expect(titles()).toEqual(["Backup failed"]);
    fireEvent.keyDown(screen.getByRole("listbox"), { key: "3" });
    expect(titles()).toEqual(["Backup failed", "Digest"]);
  });

  it("shows no reader and the empty inbox once every row is deleted", () => {
    renderTriage();
    for (const remove of screen.getAllByLabelText("Delete notification")) fireEvent.click(remove);
    expect(screen.queryAllByRole("option")).toHaveLength(0);
    expect(screen.getByText(EMPTY.notifications.title)).toBeTruthy();
    expect(screen.getByText("Select a notification.")).toBeTruthy();
  });

  it("marks the row shown on open read when it is acted on", async () => {
    renderTriage({ onSendToChat: vi.fn() });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Reply" })); });
    expect(h.markRead).toHaveBeenCalledTimes(1);
  });

  it("ignores a held key", async () => {
    const onSendToChat = vi.fn();
    renderTriage({ onSendToChat });
    const first = option("Backup failed");
    fireEvent.click(first);
    await act(async () => { fireEvent.keyDown(first, { key: "r", repeat: true }); });
    expect(onSendToChat).not.toHaveBeenCalled();
  });

  it("leads the reader with Reply and offers Open chat when the row knows its session", () => {
    const onOpenChat = vi.fn();
    h.rows = [{ ...h.ROW, session_id: "s-9" }];
    render(<NotificationsModal open onClose={() => {}} connections={[{ id: "c1", name: "casa" }]} onSelect={() => {}} onOpenChat={onOpenChat} />);
    const buttons = [...document.body.querySelector("article").querySelectorAll("button")].map((b) => b.textContent).filter(Boolean);
    expect(buttons.slice(0, 2)).toEqual(["Reply", "Open chat"]);
    fireEvent.click(screen.getByRole("button", { name: "Open chat" }));
    expect(onOpenChat).toHaveBeenCalledWith("alice", "s-9", "c1");
  });
});
