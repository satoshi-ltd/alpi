import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn(async () => []) }));
vi.mock("../primitives/Notification.jsx", () => ({ useNotify: () => vi.fn() }));
vi.mock("./ModelPicker.jsx", () => ({ default: () => null }));
vi.mock("../primitives/AttachmentChips.jsx", () => ({
  default: ({ items }) => <ul aria-label="attachments">{items.map((a) => <li key={a.path}>{a.name}</li>)}</ul>,
}));
vi.mock("../primitives/Composer.jsx", () => ({
  default: ({ value, onChange, onSubmit, canSend, topBar, mentions }) => (
    <div>
      <ul aria-label="mentions">{(mentions ?? []).map((m) => <li key={m.id}>{`${m.id}:${m.status}`}</li>)}</ul>
      <textarea aria-label="message" value={value} onChange={(e) => onChange(e.target.value)} />
      <button type="button" disabled={!canSend} onClick={onSubmit}>send</button>
      {topBar}
    </div>
  ),
}));

import { invoke } from "@tauri-apps/api/core";
import ChatComposer from "./ChatComposer.jsx";
import { clearDraft, getDraft, setDraft } from "../lib/drafts.js";

const PROFILE = { name: "scout", pubkey_b64: "pk-scout", accent: "#3899e2" };

function mount(onSend) {
  return render(<ChatComposer profiles={[PROFILE]} activeProfile={PROFILE} onSend={onSend} />);
}

async function type(text) {
  fireEvent.change(screen.getByLabelText("message"), { target: { value: text } });
}

async function send() {
  await act(async () => { fireEvent.click(screen.getByText("send")); });
}

beforeEach(() => {
  clearDraft("chat|pk-scout");
});

describe("composer send", () => {
  it("clears the box when the message is accepted", async () => {
    mount(vi.fn(async () => true));
    await type("hello");
    await send();
    expect(screen.getByLabelText("message").value).toBe("");
    expect(getDraft("chat|pk-scout")).toBe("");
  });

  it("puts the text back, and the draft, when the send is refused", async () => {
    const onSend = vi.fn(async () => false);
    mount(onSend);
    await type("a follow-up while a turn runs");
    await send();
    expect(onSend).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText("message").value).toBe("a follow-up while a turn runs");
    expect(getDraft("chat|pk-scout")).toBe("a follow-up while a turn runs");
  });

  it("puts the text back in front of anything typed while the send was pending", async () => {
    let refuse;
    mount(vi.fn(() => new Promise((resolve) => { refuse = resolve; })));
    await type("first");
    await send();
    await type("second");
    await act(async () => { refuse(false); });
    expect(screen.getByLabelText("message").value).toBe("first\n\nsecond");
  });

  it("puts the text back when the send throws", async () => {
    mount(vi.fn(async () => { throw new Error("boom"); }));
    await type("keep me");
    await send();
    expect(screen.getByLabelText("message").value).toBe("keep me");
  });

  it("treats a handler that returns nothing as accepted", async () => {
    mount(vi.fn());
    await type("hello");
    await send();
    expect(screen.getByLabelText("message").value).toBe("");
  });

  it("keeps the refused text in front of what was typed under the old profile while the send was pending", async () => {
    let refuse;
    const other = { name: "doc", pubkey_b64: "pk-doc", accent: "#f36a8a" };
    const onSend = vi.fn(() => new Promise((resolve) => { refuse = resolve; }));
    const view = render(<ChatComposer profiles={[PROFILE, other]} activeProfile={PROFILE} onSend={onSend} />);
    await type("first");
    await send();
    view.rerender(<ChatComposer profiles={[PROFILE, other]} activeProfile={other} onSend={onSend} />);
    setDraft("chat|pk-scout", "typed later");
    await act(async () => { refuse(false); });
    expect(getDraft("chat|pk-scout")).toBe("first\n\ntyped later");
    expect(screen.getByLabelText("message").value).toBe("");
  });
});

describe("peer liveness", () => {
  const probed = () => invoke.mock.calls.filter(([cmd]) => cmd === "probe_peers");
  const mountAs = (admin) =>
    render(<ChatComposer profiles={[PROFILE]} activeProfile={PROFILE} onSend={vi.fn()} canManageProfileSurfaces={admin} />);

  beforeEach(() => {
    invoke.mockReset();
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "read_file") return "- id: rook\n  alias: Rook\n";
      if (cmd === "probe_peers") return [{ id: "rook", status: "on" }];
      return [];
    });
  });

  afterEach(() => {
    invoke.mockReset();
    invoke.mockImplementation(async () => []);
  });

  it("probes the profile's peers for an admin", async () => {
    mountAs(true);
    expect(await screen.findByText("rook:on")).toBeTruthy();
    expect(probed()).toHaveLength(1);
    expect(probed()[0][1]).toEqual({ profile: "scout", ids: ["rook"] });
  });

  it("does not ask a member's daemon for the admin-only probe", async () => {
    mountAs(false);
    expect(await screen.findByText("rook:?")).toBeTruthy();
    expect(probed()).toHaveLength(0);
  });

  it("stops probing on demotion and probes again on promotion", async () => {
    const view = mountAs(true);
    await screen.findByText("rook:on");
    view.rerender(<ChatComposer profiles={[PROFILE]} activeProfile={PROFILE} onSend={vi.fn()} canManageProfileSurfaces={false} />);
    expect(await screen.findByText("rook:?")).toBeTruthy();
    expect(probed()).toHaveLength(1);
    view.rerender(<ChatComposer profiles={[PROFILE]} activeProfile={PROFILE} onSend={vi.fn()} canManageProfileSurfaces />);
    expect(await screen.findByText("rook:on")).toBeTruthy();
    expect(probed()).toHaveLength(2);
  });
});
