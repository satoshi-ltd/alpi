import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";

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
  return { ROW, DETAIL, detail: DETAIL, rows: [ROW], profileDetail: null, playTts: vi.fn(), ttsCb: { current: null } };
});

vi.mock("../lib/tts.js", () => ({
  playTts: h.playTts,
  subscribeTts: (fn) => { h.ttsCb.current = fn; return () => { h.ttsCb.current = null; }; },
  VOICE_POOL: ["en-US-AriaNeural"],
}));
vi.mock("../lib/useOnline.js", () => ({ useOnline: () => true }));
vi.mock("../lib/clipboard.js", () => ({ copyText: vi.fn(async () => true) }));
vi.mock("../primitives/Notification.jsx", () => ({ useNotify: () => () => {} }));
vi.mock("../hooks/useOutputs.js", () => ({
  useAllOutputs: () => ({ rows: h.rows, refresh: () => {} }),
  useOutput: () => ({ row: h.detail, markRead: () => {} }),
  useDeleteOutput: () => ({ schedule: () => {}, cancel: () => {} }),
  useMarkAllOutputsRead: () => () => {},
  pendingDeleteKeys: () => [],
  rowKey: (r) => `${r.connectionId}:${r.profile}:${r.id}`,
}));
vi.mock("../hooks/useProfileDetail.js", () => ({
  useProfileDetail: () => ({ detail: h.profileDetail, refresh: () => {} }),
}));

import NotificationsModal from "./NotificationsModal.jsx";

beforeEach(() => {
  h.playTts.mockClear();
  h.ttsCb.current = null;
  h.rows = [h.ROW];
  h.detail = h.DETAIL;
  h.profileDetail = null;
});

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
  it("renders the body as markdown at message-output size (profmsg/alpi-md)", () => {
    renderModal();
    const md = document.body.querySelector(".profmsg .alpi-md");
    expect(md).toBeTruthy();
    expect(md.textContent).toContain("bold");
    expect(md.querySelector("strong, b")).toBeTruthy();
  });

  it("renders the body from the list row without waiting for outputs_read", () => {
    h.detail = null;
    renderModal();
    const md = document.body.querySelector(".profmsg .alpi-md");
    expect(md?.textContent).toContain("bold");
    expect(screen.getByLabelText("Read aloud")).toBeTruthy();
  });

  it("has a read-aloud button that plays the notification body", () => {
    renderModal();
    fireEvent.click(screen.getByLabelText("Read aloud"));
    expect(h.playTts).toHaveBeenCalledTimes(1);
    expect(h.playTts.mock.calls[0][0].text).toBe(h.ROW.body);
    expect(h.playTts.mock.calls[0][0].key).toBe("notif:c1:alice:n1");
    expect(h.playTts.mock.calls[0][0].voice).toBe("en-GB-SoniaNeural");
  });

  it("switches to a Stop affordance while playing", () => {
    renderModal();
    expect(screen.queryByLabelText("Stop")).toBeNull();
    act(() => h.ttsCb.current?.({ key: "notif:c1:alice:n1", kind: "playing" }));
    expect(screen.getByLabelText("Stop")).toBeTruthy();
  });

  it("shows the connection and lowercase profile in the detail header", () => {
    renderModal([{ id: "c1", name: "casa" }, { id: "c2", name: "work" }]);
    const article = document.body.querySelector("article");
    expect(article.textContent).toContain("@alice");
    expect(article.textContent).toContain("casa");
    expect(article.textContent).not.toContain("@ALICE");
    expect(article.textContent).not.toContain("CASA");
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

    fireEvent.click(screen.getByLabelText("Read aloud"));
    expect(h.playTts.mock.calls.at(-1)[0]).toMatchObject({
      voice: "en-GB-SoniaNeural", key: "notif:c1:alice:n1",
    });

    fireEvent.click(screen.getAllByRole("option")[1]);
    fireEvent.click(screen.getByLabelText("Read aloud"));
    expect(h.playTts.mock.calls.at(-1)[0]).toMatchObject({
      voice: "fr-FR-DeniseNeural", key: "notif:c2:alice:n1",
    });
  });

  it("uses the remote profile_detail voice when summaries omits voice_id", () => {
    h.rows = [{ ...h.ROW, voice_id: undefined }];
    h.profileDetail = { voice_id: "es-ES-AlvaroNeural" };
    renderModal();
    fireEvent.click(screen.getByLabelText("Read aloud"));
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
    fireEvent.click(screen.getByLabelText("Read aloud"));
    expect(h.playTts.mock.calls.at(-1)[0].voice).toBe("en-GB-SoniaNeural");
  });
});
