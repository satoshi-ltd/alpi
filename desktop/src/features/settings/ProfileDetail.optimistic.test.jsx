import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";

const { notifySpy, stableDetail } = vi.hoisted(() => ({ notifySpy: vi.fn(), stableDetail: {} }));

vi.mock("../../hooks/useProfileDetail.js", () => ({
  useProfileDetail: () => ({ detail: stableDetail, loading: false, refresh: async () => stableDetail }),
  invalidateProfileDetailCache: () => {},
}));
vi.mock("../../hooks/useUsage.js", () => ({
  useUsageDaily: () => ({ days: [], loading: false }),
}));
vi.mock("../../primitives/Notification.jsx", () => ({ useNotify: () => notifySpy }));
vi.mock("./Usage.jsx", () => ({ default: () => null }));
vi.mock("./fields/boundaries.jsx", () => ({
  BudgetField: () => null,
  SandboxField: () => null,
  WorkspaceField: () => null,
}));
vi.mock("./fields/agent.jsx", () => ({
  AddProviderField: () => null,
  McpField: () => null,
  ModelField: ({ value, onChange }) => (
    <span data-testid="model-field" data-value={value}>
      {["m/heart", "m/cloud"].map((m) => <button key={m} onClick={() => onChange(m)}>{`model ${m}`}</button>)}
    </span>
  ),
  ReasoningEffortField: ({ value, onChange }) => (
    <span data-testid="effort-field" data-value={value}>
      {["high", "minimal"].map((e) => <button key={e} onClick={() => onChange(e)}>{`effort ${e}`}</button>)}
    </span>
  ),
  TierField: () => null,
  VisionModelField: () => null,
  FallbackModelsField: () => null,
  VoiceField: () => null,
}));
vi.mock("./fields/alp.jsx", () => ({
  PeersField: () => null,
  PipelineLimitField: () => null,
  TcpPortField: () => null,
  WorkgroupsField: () => null,
}));
vi.mock("./fields/services.jsx", () => ({ EmailCell: () => null }));
vi.mock("./fields/DaemonField.jsx", () => ({ DaemonField: () => null }));
vi.mock("./fields/network.jsx", () => ({
  NetworkAddressField: () => null,
  PairingNameField: () => null,
  PrivateRouteField: () => null,
  PublicRouteField: () => null,
}));
vi.mock("./fields/maintenance.jsx", () => ({
  DeleteProfileAction: () => null,
  StorageField: () => null,
  _clearStorageCache: () => {},
}));

import ProfileDetail from "./ProfileDetail.jsx";
import { useHostConnections } from "../../hooks/useHostConnections.js";
import { _resetProfileEdits } from "../../lib/optimisticProfiles.js";
import { _resetDaemonBus } from "../../lib/daemon-bus.js";

let saved;
let summaries;
let reloadRef;

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

const noop = () => {};
const HOST_ARGS = {
  setSessionData: noop,
  clearTurnsForConnection: noop,
  setRewriteDraft: noop,
  setActiveTask: noop,
  setView: noop,
  notify: noop,
};

function Harness() {
  const host = useHostConnections(HOST_ARGS);
  reloadRef = host.reload;
  const doc = host.profiles.find((p) => p.name === "doc");
  return (
    <>
      <ul>
        {host.profiles.map((p) => (
          <li key={p.name} data-testid={`row-${p.name}`} data-shape={p.shape} data-accent={p.accent} />
        ))}
      </ul>
      {doc && (
        <ProfileDetail
          profile={doc}
          profiles={host.profiles}
          activeConnection={{ id: "local", kind: "local" }}
          onSaved={() => host.reload()}
        />
      )}
    </>
  );
}

const row = () => screen.getByTestId("row-doc");
const heroMark = () => document.querySelector("header.ds-chat-header [data-shape]");
const saveCalls = () => invoke.mock.calls.filter(([cmd]) => cmd === "set_config_field");

beforeEach(() => {
  _resetProfileEdits();
  _resetDaemonBus();
  localStorage.clear();
  notifySpy.mockReset();
  saved = [];
  summaries = [{
    name: "doc",
    accent: "#3899e2",
    shape: "bell",
    model: "a/b",
    models: ["a/b", "m/heart", "m/cloud"],
    model_reasoning_supported: true,
    model_reasoning_effort: "low",
  }];
  invoke.mockReset();
  invoke.mockImplementation(async (cmd, args) => {
    if (cmd === "host_connections") {
      return { active_id: "local", connections: [{ id: "local", kind: "local", status: "online" }] };
    }
    if (cmd === "profile_summaries") return summaries.map((p) => ({ ...p }));
    if (cmd === "workgroups") return [];
    if (cmd === "set_config_field") {
      const d = deferred();
      saved.push({ args, ...d });
      return d.promise;
    }
    return null;
  });
});

async function mount() {
  localStorage.setItem("alf:profiles:v1:local", JSON.stringify(summaries));
  render(<Harness />);
  await waitFor(() => expect(invoke.mock.calls.some(([cmd]) => cmd === "workgroups")).toBe(true));
  await act(async () => { await reloadRef(); });
  await waitFor(() => expect(screen.getByRole("button", { name: "blue bell" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "blue bell" }));
}

describe("ProfileDetail optimistic appearance", () => {
  it("reflects a picked shape and colour in the roster and the hero before the daemon answers", async () => {
    await mount();
    fireEvent.click(screen.getByRole("button", { name: "heart" }));
    expect(row()).toHaveAttribute("data-shape", "heart");
    expect(heroMark()).toHaveAttribute("data-shape", "heart");
    expect(saveCalls()).toHaveLength(1);
    expect(saveCalls()[0][1]).toEqual({ profile: "doc", key: "tui.shape", value: "heart", connectionId: "local" });

    fireEvent.click(screen.getByRole("button", { name: "rose #f36a8a" }));
    expect(row()).toHaveAttribute("data-accent", "#f36a8a");
    expect(heroMark().querySelector("path[data-body]")).toHaveAttribute("fill", "var(--mark-body)");
    expect(heroMark().style.getPropertyValue("--mark-dark")).toBe("#f36a8a");
    expect(saveCalls()).toHaveLength(2);
    expect(saveCalls()[1][1]).toMatchObject({ key: "tui.accent", value: "#f36a8a" });
  });

  it("rolls the roster and the picker back and toasts when the save fails", async () => {
    await mount();
    fireEvent.click(screen.getByRole("button", { name: "heart" }));
    expect(row()).toHaveAttribute("data-shape", "heart");
    await act(async () => saved[0].reject(new Error("disk full")));
    expect(row()).toHaveAttribute("data-shape", "bell");
    expect(heroMark()).toHaveAttribute("data-shape", "bell");
    expect(screen.getByRole("button", { name: "bell" })).toHaveAttribute("aria-pressed", "true");
    expect(notifySpy).toHaveBeenCalledWith(expect.objectContaining({ variant: "error", message: expect.stringContaining("disk full") }));
  });

  it("sends the picks in order and ends at the last choice", async () => {
    await mount();
    fireEvent.click(screen.getByRole("button", { name: "heart" }));
    fireEvent.click(screen.getByRole("button", { name: "cloud" }));
    expect(row()).toHaveAttribute("data-shape", "cloud");
    expect(saved).toHaveLength(1);
    summaries = [{ ...summaries[0], shape: "cloud" }];
    await act(async () => saved[0].resolve(null));
    await waitFor(() => expect(saved).toHaveLength(2));
    await act(async () => saved[1].resolve(null));
    await waitFor(() => expect(invoke.mock.calls.filter(([c]) => c === "profile_summaries").length).toBeGreaterThan(1));
    await act(async () => { await reloadRef(); });
    expect(row()).toHaveAttribute("data-shape", "cloud");
    expect(heroMark()).toHaveAttribute("data-shape", "cloud");
  });

  it("keeps the last choice when the first save fails after the second", async () => {
    await mount();
    fireEvent.click(screen.getByRole("button", { name: "heart" }));
    fireEvent.click(screen.getByRole("button", { name: "cloud" }));
    await act(async () => saved[0].reject(new Error("late")));
    expect(row()).toHaveAttribute("data-shape", "cloud");
  });

  it("a roster refresh landing during the save does not revert the pick", async () => {
    await mount();
    fireEvent.click(screen.getByRole("button", { name: "heart" }));
    await act(async () => { await reloadRef(); });
    expect(row()).toHaveAttribute("data-shape", "heart");
    expect(heroMark()).toHaveAttribute("data-shape", "heart");
    summaries = [{ ...summaries[0], shape: "heart" }];
    await act(async () => saved[0].resolve(null));
    await act(async () => { await reloadRef(); });
    expect(row()).toHaveAttribute("data-shape", "heart");
  });

  it("trusts the daemon once the save landed and a fresh roster arrived", async () => {
    await mount();
    fireEvent.click(screen.getByRole("button", { name: "heart" }));
    await act(async () => saved[0].resolve(null));
    summaries = [{ ...summaries[0], shape: "pebble" }];
    await act(async () => { await reloadRef(); });
    await waitFor(() => expect(row()).toHaveAttribute("data-shape", "pebble"));
  });

  it.each([
    ["shape", "heart", "cloud", () => ["bell", "heart", "cloud"].find((n) => screen.getByRole("button", { name: n }).getAttribute("aria-pressed") === "true")],
    ["model", "model m/heart", "model m/cloud", () => screen.getByTestId("model-field").dataset.value],
    ["effort", "effort high", "effort minimal", () => screen.getByTestId("effort-field").dataset.value],
  ])("two failed %s picks in a row end on the daemon value", async (field, first, second, picked) => {
    await mount();
    const daemon = { shape: "bell", model: "a/b", effort: "low" }[field];
    fireEvent.click(screen.getByRole("button", { name: first }));
    fireEvent.click(screen.getByRole("button", { name: second }));
    await act(async () => saved[0].reject(new Error("offline")));
    await waitFor(() => expect(saved).toHaveLength(2));
    await act(async () => saved[1].reject(new Error("offline")));
    await act(async () => { await reloadRef(); });
    expect(picked()).toBe(daemon);
    if (field === "shape") {
      expect(row()).toHaveAttribute("data-shape", "bell");
      expect(heroMark()).toHaveAttribute("data-shape", "bell");
    }
  });

  it("keeps typed hex on the debounce", async () => {
    await mount();
    fireEvent.change(screen.getByPlaceholderText("#hex"), { target: { value: "#123abc" } });
    expect(saveCalls()).toHaveLength(0);
    await waitFor(() => expect(saveCalls()).toHaveLength(1));
  });
});
