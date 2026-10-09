import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn(async () => []) }));
vi.mock("../primitives/Notification.jsx", () => ({ useNotify: () => vi.fn() }));
vi.mock("./ModelPicker.jsx", () => ({ default: () => null }));
vi.mock("../primitives/AttachmentChips.jsx", () => ({
  default: ({ items }) => <ul aria-label="attachments">{items.map((a) => <li key={a.path}>{a.name}</li>)}</ul>,
}));
vi.mock("../primitives/Composer.jsx", () => ({
  default: ({ value, onChange, onSubmit, canSend, topBar }) => (
    <div>
      <textarea aria-label="message" value={value} onChange={(e) => onChange(e.target.value)} />
      <button type="button" disabled={!canSend} onClick={onSubmit}>send</button>
      {topBar}
    </div>
  ),
}));

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
