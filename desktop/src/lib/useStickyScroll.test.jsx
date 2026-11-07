import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, act } from "@testing-library/react";
import { StrictMode } from "react";
import { followKey, useStickyScroll } from "./useStickyScroll.js";

let rafQueue = [];
const flushRaf = () => {
  const q = rafQueue;
  rafQueue = [];
  q.forEach((cb) => cb && cb());
};

beforeEach(() => {
  rafQueue = [];
  vi.stubGlobal("requestAnimationFrame", (cb) => rafQueue.push(cb));
  vi.stubGlobal("cancelAnimationFrame", (id) => { rafQueue[id - 1] = null; });
});
afterEach(() => vi.unstubAllGlobals());

function makeScrollable(node, { scrollHeight, clientHeight }) {
  let top = 0;
  Object.defineProperty(node, "scrollHeight", { configurable: true, get: () => scrollHeight });
  Object.defineProperty(node, "clientHeight", { configurable: true, get: () => clientHeight });
  Object.defineProperty(node, "scrollTop", {
    configurable: true,
    get: () => top,
    set: (v) => { top = v; },
  });
}

function Harness({ tick, stickKey, nodeRef, mounted = true, resetKey }) {
  const ref = useStickyScroll([tick], stickKey, resetKey);
  if (!mounted) return <p>loading</p>;
  return (
    <div
      ref={(n) => {
        ref.current = n;
        if (n) nodeRef.current = n;
      }}
    />
  );
}

function setup({ stickKey = "k" } = {}) {
  const nodeRef = { current: null };
  const { rerender } = render(<Harness tick={0} stickKey={stickKey} nodeRef={nodeRef} />);
  const node = nodeRef.current;
  makeScrollable(node, { scrollHeight: 1000, clientHeight: 500 });
  node.scrollTop = 500;
  return { node, nodeRef, rerender };
}

const scrollUp = (node, top, scrollHeight) => {
  if (scrollHeight != null) {
    Object.defineProperty(node, "scrollHeight", { configurable: true, get: () => scrollHeight });
  }
  node.scrollTop = top;
  act(() => { node.dispatchEvent(new Event("scroll")); });
};

describe("useStickyScroll", () => {
  it("follows new content while pinned to the bottom", () => {
    const { node, nodeRef, rerender } = setup();
    Object.defineProperty(node, "scrollHeight", { configurable: true, get: () => 1200 });
    act(() => rerender(<Harness tick={1} stickKey="k" nodeRef={nodeRef} />));
    act(() => flushRaf());
    expect(node.scrollTop).toBe(1200);
  });

  it("does NOT yank back to bottom when the user scrolls up between schedule and paint", () => {
    const { node, nodeRef, rerender } = setup();
    act(() => rerender(<Harness tick={1} stickKey="k" nodeRef={nodeRef} />));
    scrollUp(node, 100, 1200);
    act(() => flushRaf());
    expect(node.scrollTop).toBe(100);
  });

  it("stays put on further output once the user has scrolled up", () => {
    const { node, nodeRef, rerender } = setup();
    scrollUp(node, 100, 1200);
    act(() => rerender(<Harness tick={1} stickKey="k" nodeRef={nodeRef} />));
    act(() => flushRaf());
    expect(node.scrollTop).toBe(100);
  });

  it("re-engages following when the stick key changes (new message sent)", () => {
    const { node, nodeRef, rerender } = setup();
    scrollUp(node, 100, 1200);
    act(() => rerender(<Harness tick={1} stickKey="k2" nodeRef={nodeRef} />));
    act(() => flushRaf());
    expect(node.scrollTop).toBe(1200);
  });

  it("does not re-engage when the key goes back to null (the stream ended)", () => {
    const { node, nodeRef, rerender } = setup();
    scrollUp(node, 100, 1200);
    act(() => rerender(<Harness tick={1} stickKey={null} nodeRef={nodeRef} />));
    act(() => flushRaf());
    expect(node.scrollTop).toBe(100);
  });

  it("does not re-engage when the same key returns after a null gap", () => {
    const { node, nodeRef, rerender } = setup();
    scrollUp(node, 100, 1200);
    act(() => rerender(<Harness tick={1} stickKey={null} nodeRef={nodeRef} />));
    act(() => rerender(<Harness tick={2} stickKey="k" nodeRef={nodeRef} />));
    act(() => flushRaf());
    expect(node.scrollTop).toBe(100);
  });

  it("listens to a container that mounts after the first render", () => {
    const nodeRef = { current: null };
    const { rerender } = render(<Harness tick={0} stickKey="k" nodeRef={nodeRef} mounted={false} />);
    act(() => rerender(<Harness tick={1} stickKey="k" nodeRef={nodeRef} />));
    const node = nodeRef.current;
    makeScrollable(node, { scrollHeight: 1000, clientHeight: 500 });
    act(() => flushRaf());
    scrollUp(node, 100, 1200);
    act(() => rerender(<Harness tick={2} stickKey="k" nodeRef={nodeRef} />));
    act(() => flushRaf());
    expect(node.scrollTop).toBe(100);
  });
  it("lands at the bottom of another transcript after scrolling up in this one", () => {
    const { node, nodeRef, rerender } = setup();
    scrollUp(node, 100, 1200);
    act(() => rerender(<Harness tick={1} stickKey={null} nodeRef={nodeRef} resetKey={2} />));
    act(() => flushRaf());
    expect(node.scrollTop).toBe(1200);
  });

  it("keeps listening under StrictMode's simulated remount", () => {
    const nodeRef = { current: null };
    const { rerender } = render(<StrictMode><Harness tick={0} stickKey="k" nodeRef={nodeRef} /></StrictMode>);
    const node = nodeRef.current;
    makeScrollable(node, { scrollHeight: 1000, clientHeight: 500 });
    act(() => flushRaf());
    scrollUp(node, 100, 1200);
    act(() => rerender(<StrictMode><Harness tick={1} stickKey="k" nodeRef={nodeRef} /></StrictMode>));
    act(() => flushRaf());
    expect(node.scrollTop).toBe(100);
  });
});

describe("followKey", () => {
  const scope = "local:p";
  const pending = { requestId: "r1" };

  it("keeps the sent turn's id from pending through tail and drops it when the turn is done", () => {
    let f = followKey(null, { scope, sessionId: "s", pendingTurn: pending, lastTurnInFlight: false });
    expect(f.key).toBe("r1");
    f = followKey(f, { scope, sessionId: "s", pendingTurn: null, lastTurnInFlight: false });
    expect(f.key).toBe(null);
    f = followKey(f, { scope, sessionId: "s", pendingTurn: null, lastTurnInFlight: true });
    expect(f.key).toBe("r1");
    f = followKey(f, { scope, sessionId: "s", pendingTurn: null, lastTurnInFlight: false });
    expect(f.key).toBe(null);
  });

  it("gives a new send a new key and an in-flight session opened elsewhere a tail key", () => {
    let f = followKey(null, { scope, sessionId: "s", pendingTurn: pending, lastTurnInFlight: false });
    f = followKey(f, { scope, sessionId: "s", pendingTurn: { requestId: "r2" }, lastTurnInFlight: false });
    expect(f.key).toBe("r2");
    f = followKey(f, { scope, sessionId: "other", pendingTurn: null, lastTurnInFlight: true });
    expect(f.key).toBe("tail:2");
  });

  it("counts a transcript per session, with a new chat becoming a session as the same one", () => {
    let f = followKey(null, { scope, sessionId: null, pendingTurn: pending, lastTurnInFlight: false });
    expect(f.transcript).toBe(1);
    f = followKey(f, { scope, sessionId: "s1", pendingTurn: pending, lastTurnInFlight: false });
    expect(f.transcript).toBe(1);
    expect(f.key).toBe("r1");
    f = followKey(f, { scope, sessionId: "s1", pendingTurn: null, lastTurnInFlight: false });
    expect(f.transcript).toBe(1);
    expect(f.key).toBe(null);
    f = followKey(f, { scope, sessionId: "s2", pendingTurn: null, lastTurnInFlight: false });
    expect(f.transcript).toBe(2);
    f = followKey(f, { scope: "local:q", sessionId: "s2", pendingTurn: null, lastTurnInFlight: false });
    expect(f.transcript).toBe(3);
    f = followKey(f, { scope: "local:q", sessionId: null, pendingTurn: null, lastTurnInFlight: false });
    expect(f.transcript).toBe(4);
  });

  it("counts leaving a streaming new chat for another session as a new transcript", () => {
    let f = followKey(null, { scope, sessionId: null, pendingTurn: pending, lastTurnInFlight: false });
    f = followKey(f, { scope, sessionId: "b", pendingTurn: null, lastTurnInFlight: false });
    expect(f.transcript).toBe(2);
  });
});
