import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { DONE_MS, sessionMarkState, useSessionMark } from "./sessionMark.js";

const live = { requestId: "r1" };
const run = (initial) => renderHook((props) => useSessionMark(props), { initialProps: { scope: "c:doc", ...initial } });

describe("useSessionMark", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("is idle with no turn and works from send until the turn ends, through thinking, streaming and tools", () => {
    const { result, rerender } = run({ turn: null });
    expect(result.current).toBe("idle");
    rerender({ scope: "c:doc", turn: live });
    expect(result.current).toBe("working");
    rerender({ scope: "c:doc", turn: { ...live, assistantPreview: "hel", tools: [{ name: "grep" }] } });
    expect(result.current).toBe("working");
  });

  it("shows done for a moment after a successful turn, then idle", () => {
    const { result, rerender } = run({ turn: live });
    rerender({ scope: "c:doc", turn: null });
    expect(result.current).toBe("done");
    act(() => vi.advanceTimersByTime(DONE_MS - 100));
    expect(result.current).toBe("done");
    act(() => vi.advanceTimersByTime(200));
    expect(result.current).toBe("idle");
    expect(DONE_MS).toBe(2400);
  });

  it("reads a settling turn as finished", () => {
    const { result, rerender } = run({ turn: live });
    rerender({ scope: "c:doc", turn: { ...live, settling: true } });
    expect(result.current).toBe("done");
  });

  it("shows failed when the turn ends in an error, until the next send", () => {
    const { result, rerender } = run({ turn: live });
    rerender({ scope: "c:doc", turn: { ...live, error: "boom", ended: true } });
    expect(result.current).toBe("failed");
    act(() => vi.advanceTimersByTime(DONE_MS * 3));
    expect(result.current).toBe("failed");
    rerender({ scope: "c:doc", turn: null });
    expect(result.current).toBe("failed");
    rerender({ scope: "c:doc", turn: { requestId: "r2" } });
    expect(result.current).toBe("working");
  });

  it("returns to idle, not done, when the user cancels the turn", () => {
    const { result, rerender } = run({ turn: live });
    rerender({ scope: "c:doc", turn: { ...live, interrupted: true } });
    expect(result.current).toBe("idle");
    rerender({ scope: "c:doc", turn: null });
    expect(result.current).toBe("idle");
    rerender({ scope: "c:doc", turn: { requestId: "r2" } });
    rerender({ scope: "c:doc", turn: null });
    expect(result.current).toBe("done");
  });

  it("needs you while a question or a permission request is pending, over working", () => {
    const { result, rerender } = run({ turn: live, needs: true });
    expect(result.current).toBe("needs");
    rerender({ scope: "c:doc", turn: live, needs: false });
    expect(result.current).toBe("working");
  });

  it("is paused when the profile is paused, over everything else", () => {
    const { result } = run({ turn: live, needs: true, paused: true });
    expect(result.current).toBe("paused");
  });

  it("forgets a done or failed state when the chat moves to another profile", () => {
    const { result, rerender } = run({ turn: live });
    rerender({ scope: "c:doc", turn: { ...live, error: "x", ended: true } });
    expect(result.current).toBe("failed");
    rerender({ scope: "c:abby", turn: null });
    expect(result.current).toBe("idle");
  });
});

describe("useSessionMark across sessions of one profile", () => {
  const mount = (initial) => renderHook((props) => useSessionMark(props), { initialProps: { scope: "c:doc", ...initial } });

  it("shows no false done when the chat moves to another session of the same profile mid-turn", () => {
    vi.useFakeTimers();
    const { result, rerender } = mount({ session: "s_a", turn: live });
    expect(result.current).toBe("working");
    rerender({ scope: "c:doc", session: "s_b", turn: null });
    expect(result.current).toBe("idle");
    act(() => vi.advanceTimersByTime(DONE_MS * 2));
    expect(result.current).toBe("idle");
    vi.useRealTimers();
  });

  it("does not carry a failed turn into another session of the same profile", () => {
    const { result, rerender } = mount({ session: "s_a", turn: live });
    rerender({ scope: "c:doc", session: "s_a", turn: { ...live, error: "boom", ended: true } });
    expect(result.current).toBe("failed");
    rerender({ scope: "c:doc", session: "s_b", turn: null });
    expect(result.current).toBe("idle");
  });

  it("keeps the done of a new thread when the turn names its session, and drops it on the next switch", () => {
    const { result, rerender } = mount({ session: null, turn: live });
    rerender({ scope: "c:doc", session: null, turn: null });
    expect(result.current).toBe("done");
    rerender({ scope: "c:doc", session: "s_new", turn: null });
    expect(result.current).toBe("done");
    rerender({ scope: "c:doc", session: "s_other", turn: null });
    expect(result.current).toBe("idle");
  });
});

describe("sessionMarkState", () => {
  it("orders paused, needs, working, then what the last turn left", () => {
    expect(sessionMarkState({})).toBe("idle");
    expect(sessionMarkState({ after: "done" })).toBe("done");
    expect(sessionMarkState({ turn: live, after: "failed" })).toBe("working");
    expect(sessionMarkState({ turn: live, needs: true })).toBe("needs");
    expect(sessionMarkState({ turn: live, needs: true, paused: true })).toBe("paused");
  });
});
