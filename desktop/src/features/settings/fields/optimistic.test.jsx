import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const h = vi.hoisted(() => ({ invoke: vi.fn(), notify: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => ({ invoke: h.invoke }));
vi.mock("../../../primitives/Notification.jsx", () => ({ useNotify: () => h.notify }));

import { VisionModelField } from "./VisionModelField.jsx";
import { TierField } from "./TierField.jsx";
import { BudgetField } from "./boundaries.jsx";
import { useProfileSnapshot, _clearProfileSnapshotCache } from "../../../hooks/useProfileSnapshot.js";
import {
  DETAIL_ONLY_FIELDS,
  _resetProfileEdits,
  applyEdits,
  editClock,
  releaseLanded,
  useProfileEdits,
} from "../../../lib/optimisticProfiles.js";

let pending;
let snapshots;

function detailRead(detail) {
  let land;
  let fail;
  const read = vi.fn(() => {
    const since = editClock();
    return new Promise((resolve, reject) => {
      land = () => { releaseLanded("local", since, [{ name: "work", ...detail }], DETAIL_ONLY_FIELDS); resolve(); };
      fail = () => reject(new Error("offline"));
    });
  });
  return { read, land: () => land(), fail: () => fail() };
}

beforeEach(() => {
  _resetProfileEdits();
  h.notify.mockReset();
  h.invoke.mockReset();
  _clearProfileSnapshotCache();
  pending = [];
  snapshots = [];
  h.invoke.mockImplementation((cmd) => {
    if (cmd === "set_config_field" || cmd === "unset_config_field") {
      return new Promise((resolve, reject) => pending.push({ resolve, reject }));
    }
    if (cmd === "settings_profile_snapshot") {
      return new Promise((resolve) => snapshots.push(resolve));
    }
    return Promise.resolve([]);
  });
});

const PROFILE = {
  name: "work",
  model: "openrouter/main",
  models: ["openrouter/main", "openrouter/deepseek/vision"],
  vision_model: "openrouter/deepseek/vision",
  budget_daily_usd: 5,
  tiers: { fast: { model: "openrouter/main", effort: "", reasoning_supported: false } },
};
const shown = () => applyEdits(PROFILE, "local");

describe("discrete profile fields save optimistically", () => {
  it("vision model shows the choice before the answer and rolls back with a toast on failure", async () => {
    render(<VisionModelField profile={PROFILE} connectionId="local" />);
    fireEvent.click(screen.getByText("Clear"));
    expect(shown().vision_model).toBe("");
    expect(h.invoke.mock.calls.filter(([c]) => c === "set_config_field")).toHaveLength(1);
    await act(async () => pending[0].reject(new Error("nope")));
    expect(shown().vision_model).toBe("openrouter/deepseek/vision");
    expect(h.notify).toHaveBeenCalledWith(expect.objectContaining({ variant: "error" }));
  });

  it("vision model keeps the choice until the refreshed detail lands", async () => {
    const detail = detailRead({ vision_model: "" });
    render(<VisionModelField profile={PROFILE} connectionId="local" onSaved={detail.read} />);
    fireEvent.click(screen.getByText("Clear"));
    await act(async () => pending[0].resolve(null));
    expect(detail.read).toHaveBeenCalledTimes(1);
    expect(shown().vision_model).toBe("");
    await act(async () => detail.land());
    expect(shown().vision_model).toBe("openrouter/deepseek/vision");
  });

  it("a refresh that fails after the save keeps the choice shown", async () => {
    const detail = detailRead({ vision_model: "" });
    render(<VisionModelField profile={PROFILE} connectionId="local" onSaved={detail.read} />);
    fireEvent.click(screen.getByText("Clear"));
    await act(async () => pending[0].resolve(null));
    await act(async () => detail.fail());
    expect(shown().vision_model).toBe("");
  });

  it("a tier save whose first snapshot is superseded keeps the tier until the newer snapshot lands", async () => {
    function Harness() {
      useProfileEdits();
      const snap = useProfileSnapshot("local", "work");
      const profile = applyEdits({ ...PROFILE, ...(snap.snapshot?.detail ?? {}) }, "local");
      return (
        <>
          <span data-testid="tier">{profile.tiers.fast.model}</span>
          <button onClick={() => snap.refresh()}>reload</button>
          <TierField profile={profile} name="fast" connectionId="local" onSaved={snap.refresh} />
        </>
      );
    }
    const tier = () => screen.getByTestId("tier").textContent;
    render(<Harness />);
    const daemonBefore = { detail: { tiers: PROFILE.tiers } };
    await act(async () => snapshots[0](daemonBefore));
    fireEvent.click(screen.getByText("Clear"));
    expect(tier()).toBe("");
    await act(async () => pending[0].resolve(null));
    expect(snapshots).toHaveLength(2);
    fireEvent.click(screen.getByText("reload"));
    expect(snapshots).toHaveLength(3);
    await act(async () => snapshots[1](daemonBefore));
    expect(tier()).toBe("");
    const cleared = { detail: { tiers: { fast: { model: "", effort: "", reasoning_supported: false } } } };
    await act(async () => snapshots[2](cleared));
    expect(tier()).toBe("");
    expect(shown().tiers.fast.model).toBe("openrouter/main");
  });

  it("clearing a tier empties it at once", async () => {
    render(<TierField profile={PROFILE} name="fast" connectionId="local" />);
    fireEvent.click(screen.getByText("Clear"));
    expect(shown().tiers.fast.model).toBe("");
    expect(h.invoke).toHaveBeenCalledWith("unset_config_field", { profile: "work", key: "tiers.fast", connectionId: "local" });
    await act(async () => pending[0].reject(new Error("nope")));
    expect(shown().tiers.fast.model).toBe("openrouter/main");
  });

  it("budget shows the new cap before the answer and restores it on failure", async () => {
    render(<BudgetField profile={PROFILE} connectionId="local" />);
    fireEvent.click(screen.getByRole("button", { name: /\$5\.00/ }));
    fireEvent.change(screen.getByPlaceholderText("empty = unlimited"), { target: { value: "12" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(shown().budget_daily_usd).toBe(12);
    await act(async () => pending[0].reject(new Error("nope")));
    expect(shown().budget_daily_usd).toBe(5);
    expect(h.notify).toHaveBeenCalledWith(expect.objectContaining({ message: "budget: Error: nope" }));
  });

  it.each([
    ["vision model", () => <VisionModelField profile={PROFILE} connectionId="conn-b" />, () => fireEvent.click(screen.getByText("Clear"))],
    ["tier", () => <TierField profile={PROFILE} name="fast" connectionId="conn-b" />, () => fireEvent.click(screen.getByText("Clear"))],
    ["budget", () => <BudgetField profile={PROFILE} connectionId="conn-b" />, () => {
      fireEvent.click(screen.getByRole("button", { name: /\$5\.00/ }));
      fireEvent.change(screen.getByPlaceholderText("empty = unlimited"), { target: { value: "12" } });
      fireEvent.click(screen.getByRole("button", { name: "Save" }));
    }],
  ])("%s writes to the connection the edit is keyed by", (_label, field, act_) => {
    render(field());
    act_();
    const writes = h.invoke.mock.calls.filter(([c]) => c === "set_config_field" || c === "unset_config_field");
    expect(writes).toHaveLength(1);
    expect(writes[0][1].connectionId).toBe("conn-b");
    expect(applyEdits(PROFILE, "conn-b")).not.toEqual(PROFILE);
  });

  it("a failed tier clear over a confirmed one refreshes and then shows what the daemon has", async () => {
    const detail = detailRead({ tiers: PROFILE.tiers });
    const onSaved = detail.read;
    const land = detail.land;
    render(<TierField profile={PROFILE} name="fast" connectionId="local" onSaved={onSaved} />);
    fireEvent.click(screen.getByText("Clear"));
    fireEvent.click(screen.getByText("Clear"));
    await act(async () => pending[0].resolve(null));
    expect(shown().tiers.fast.model).toBe("");
    await vi.waitFor(() => expect(pending).toHaveLength(2));
    await act(async () => pending[1].reject(new Error("nope")));
    expect(onSaved).toHaveBeenCalledTimes(1);
    expect(shown().tiers.fast.model).toBe("");
    await act(async () => land());
    expect(shown().tiers.fast.model).toBe("openrouter/main");
  });
});
