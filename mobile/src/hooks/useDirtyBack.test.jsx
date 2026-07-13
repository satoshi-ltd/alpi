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

const alertMock = vi.fn();
vi.mock("react-native", () => ({ Alert: { alert: (...a) => alertMock(...a) } }));

import { useDirtyBack } from "./useDirtyBack";

function fireBeforeRemove() {
  const e = { preventDefault: vi.fn(), data: { action: { type: "GO_BACK" } } };
  act(() => { listener?.(e); });
  return e;
}

function buttons() {
  return alertMock.mock.calls.at(-1)[2];
}

beforeEach(() => {
  listener = null;
  nav.setOptions.mockClear();
  nav.dispatch.mockClear();
  nav.addListener.mockClear();
  alertMock.mockClear();
});

describe("useDirtyBack", () => {
  it("lets a clean back through without prompting", () => {
    renderHook(() => useDirtyBack(false, () => {}));
    const e = fireBeforeRemove();
    expect(e.preventDefault).not.toHaveBeenCalled();
    expect(alertMock).not.toHaveBeenCalled();
  });

  it("intercepts the native back gesture and prompts when dirty", () => {
    renderHook(() => useDirtyBack(true, () => {}));
    const e = fireBeforeRemove();
    expect(e.preventDefault).toHaveBeenCalled();
    expect(alertMock).toHaveBeenCalledTimes(1);
  });

  it("dispatches the original action on Discard and lets the re-fired event pass", () => {
    renderHook(() => useDirtyBack(true, () => {}));
    const first = fireBeforeRemove();
    expect(first.preventDefault).toHaveBeenCalled();
    act(() => { buttons().find((b) => b.text === "Discard").onPress(); });
    expect(nav.dispatch).toHaveBeenCalledWith({ type: "GO_BACK" });

    const second = fireBeforeRemove();
    expect(second.preventDefault).not.toHaveBeenCalled();
  });

  it("keeps the prompt dismissable so a later back can prompt again", () => {
    renderHook(() => useDirtyBack(true, () => {}));
    fireBeforeRemove();
    act(() => { buttons().find((b) => b.text === "Keep editing").onPress(); });
    const again = fireBeforeRemove();
    expect(again.preventDefault).toHaveBeenCalled();
    expect(alertMock).toHaveBeenCalledTimes(2);
  });

  it("disables the swipe gesture only while dirty", () => {
    const { rerender } = renderHook(({ d }) => useDirtyBack(d, () => {}), { initialProps: { d: false } });
    expect(nav.setOptions).toHaveBeenLastCalledWith({ gestureEnabled: true });
    rerender({ d: true });
    expect(nav.setOptions).toHaveBeenLastCalledWith({ gestureEnabled: false });
  });

  it("returns an ask() that triggers the leave attempt", () => {
    const leave = vi.fn();
    const { result } = renderHook(() => useDirtyBack(false, leave));
    act(() => { result.current(); });
    expect(leave).toHaveBeenCalled();
  });
});
