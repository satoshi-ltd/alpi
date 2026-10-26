import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

let listener = null;
const nav = {
  setOptions: vi.fn(),
  dispatch: vi.fn(),
  addListener: vi.fn((event, fn) => {
    if (event === "beforeRemove") listener = fn;
    return () => { listener = null; };
  }),
};
vi.mock("expo-router", () => ({ useNavigation: () => nav }));

const confirmMock = vi.fn();
vi.mock("../components/ConfirmProvider", () => ({ useConfirm: () => confirmMock }));

import { useDirtyBack } from "./useDirtyBack";

function fireBeforeRemove() {
  const e = { preventDefault: vi.fn(), data: { action: { type: "GO_BACK" } } };
  act(() => { listener?.(e); });
  return e;
}

let answer;
const answerWith = async (value) => { await act(async () => { answer(value); }); };

beforeEach(() => {
  listener = null;
  nav.setOptions.mockClear();
  nav.dispatch.mockClear();
  nav.addListener.mockClear();
  confirmMock.mockReset();
  confirmMock.mockImplementation(() => new Promise((resolve) => { answer = resolve; }));
});

describe("useDirtyBack", () => {
  it("lets a clean back through without prompting", () => {
    renderHook(() => useDirtyBack(false, () => {}));
    const e = fireBeforeRemove();
    expect(e.preventDefault).not.toHaveBeenCalled();
    expect(confirmMock).not.toHaveBeenCalled();
  });

  it("intercepts the native back gesture and prompts when dirty", () => {
    renderHook(() => useDirtyBack(true, () => {}));
    const e = fireBeforeRemove();
    expect(e.preventDefault).toHaveBeenCalled();
    expect(confirmMock).toHaveBeenCalledTimes(1);
    expect(confirmMock.mock.calls[0][0]).toMatchObject({ confirmLabel: "Discard", cancelLabel: "Keep editing" });
  });

  it("dispatches the original action on Discard and lets the re-fired event pass", async () => {
    renderHook(() => useDirtyBack(true, () => {}));
    const first = fireBeforeRemove();
    expect(first.preventDefault).toHaveBeenCalled();
    await answerWith(true);
    expect(nav.dispatch).toHaveBeenCalledWith({ type: "GO_BACK" });

    const second = fireBeforeRemove();
    expect(second.preventDefault).not.toHaveBeenCalled();
  });

  it("keeps the prompt dismissable so a later back can prompt again", async () => {
    renderHook(() => useDirtyBack(true, () => {}));
    fireBeforeRemove();
    await answerWith(false);
    expect(nav.dispatch).not.toHaveBeenCalled();
    const again = fireBeforeRemove();
    expect(again.preventDefault).toHaveBeenCalled();
    expect(confirmMock).toHaveBeenCalledTimes(2);
  });

  it("disables the swipe gesture only while dirty", () => {
    const { rerender } = renderHook(({ d }) => useDirtyBack(d, () => {}), { initialProps: { d: false } });
    expect(nav.setOptions).toHaveBeenLastCalledWith({ gestureEnabled: true });
    rerender({ d: true });
    expect(nav.setOptions).toHaveBeenLastCalledWith({ gestureEnabled: false });
  });

  it("gives the swipe back when the editor goes away while dirty, so the screen under it is not left locked", () => {
    const view = renderHook(() => useDirtyBack(true, () => {}));
    expect(nav.setOptions).toHaveBeenLastCalledWith({ gestureEnabled: false });
    view.unmount();
    expect(nav.setOptions).toHaveBeenLastCalledWith({ gestureEnabled: true });
  });

  it("returns an ask() that triggers the leave attempt", () => {
    const leave = vi.fn();
    const { result } = renderHook(() => useDirtyBack(false, leave));
    act(() => { result.current(); });
    expect(leave).toHaveBeenCalled();
  });
});
