import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const invoke = vi.fn(async () => []);
const notify = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({ invoke: (...args) => invoke(...args) }));
vi.mock("../primitives/Notification.jsx", () => ({ useNotify: () => notify }));

import ChatComposer from "./ChatComposer.jsx";
import { clearDraft } from "../lib/drafts.js";

const PROFILE = {
  name: "scout",
  pubkey_b64: "pk-scout",
  model: "a/x",
  model_reasoning_supported: true,
  model_reasoning_effort: "medium",
};

function mount(props = {}) {
  return render(
    <ChatComposer
      profiles={[PROFILE]}
      activeProfile={PROFILE}
      availableModels={["a/x", "a/y"]}
      onSend={vi.fn()}
      {...props}
    />,
  );
}

beforeEach(() => {
  clearDraft("chat|pk-scout");
  invoke.mockReset();
  invoke.mockImplementation(async () => []);
  notify.mockReset();
});

describe("ChatComposer paused and offline", () => {
  it("shows no status row and no Resume while paused, even after typing", () => {
    mount({ activeProfile: { ...PROFILE, paused: true }, paused: true });
    expect(screen.getByPlaceholderText("Paused — resume to chat")).toBeDisabled();
    fireEvent.change(screen.getByPlaceholderText("Paused — resume to chat"), { target: { value: "x" } });
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.queryByRole("button", { name: "Resume" })).toBeNull();
  });

  it("says why sending is paused when the daemon is offline, with no Resume", () => {
    mount({ daemonOffline: true });
    expect(screen.getByRole("status")).toHaveTextContent("Daemon offline — sending paused");
    expect(screen.queryByRole("button", { name: "Resume" })).toBeNull();
    expect(screen.getByPlaceholderText("Message scout…")).toBeInTheDocument();
  });

  it("shows no reason when the composer is usable", () => {
    mount();
    expect(screen.queryByRole("status")).toBeNull();
  });
});

describe("ChatComposer model and effort", () => {
  it("carries the effort in the model label", () => {
    mount();
    expect(screen.getByRole("button", { name: /x/ })).toHaveTextContent("x · medium");
  });

  it("applies an effort pick through the same config field settings use, without a Save", async () => {
    mount({ connectionId: "c1" });
    fireEvent.click(screen.getByText("x").closest("button"));
    fireEvent.click(screen.getByRole("radio", { name: "High" }));
    expect(invoke).toHaveBeenCalledWith("set_config_field", {
      profile: "scout",
      key: "model_reasoning.effort",
      value: "high",
      connectionId: "c1",
    });
    expect(screen.getByRole("radio", { name: "High" })).toHaveAttribute("aria-checked", "true");
  });

  it("refreshes the profiles after a saved effort so a remount shows it", async () => {
    const onProfileSaved = vi.fn();
    const view = mount({ onProfileSaved });
    fireEvent.click(screen.getByText("x").closest("button"));
    fireEvent.click(screen.getByRole("radio", { name: "High" }));
    await waitFor(() => expect(onProfileSaved).toHaveBeenCalledTimes(1));
    view.unmount();
    mount({ activeProfile: { ...PROFILE, model_reasoning_effort: "high" } });
    expect(screen.getByRole("button", { name: /x/ })).toHaveTextContent("x · high");
  });

  it("does not refresh when the save fails", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "set_config_field") throw new Error("nope");
      return [];
    });
    const onProfileSaved = vi.fn();
    mount({ onProfileSaved });
    fireEvent.click(screen.getByText("x").closest("button"));
    fireEvent.click(screen.getByRole("radio", { name: "Low" }));
    await waitFor(() => expect(notify).toHaveBeenCalled());
    expect(onProfileSaved).not.toHaveBeenCalled();
  });

  it("reverts and reports when the daemon refuses the effort", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "set_config_field") throw new Error("nope");
      return [];
    });
    mount();
    fireEvent.click(screen.getByText("x").closest("button"));
    fireEvent.click(screen.getByRole("radio", { name: "Low" }));
    await waitFor(() => expect(notify).toHaveBeenCalledWith(expect.objectContaining({ variant: "error" })));
    expect(screen.getByRole("radio", { name: "Medium" })).toHaveAttribute("aria-checked", "true");
  });

  it("hides the effort row for a model without reasoning", () => {
    mount({ activeProfile: { ...PROFILE, model_reasoning_supported: false } });
    fireEvent.click(screen.getByRole("button", { name: /x/ }));
    expect(screen.queryByRole("radiogroup")).toBeNull();
  });
});
