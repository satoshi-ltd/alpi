import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";

import RelativeTime from "./RelativeTime.jsx";
import { TICK_MS } from "../hooks/useNow.js";
import { relativeTime } from "../lib/time.js";

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-08-05T12:00:00Z"));
});

afterEach(() => {
  vi.useRealTimers();
});

const secondsNow = () => Date.now() / 1000;

describe("RelativeTime", () => {
  it("keeps tracking the clock without any other render", () => {
    render(<span data-testid="stamp"><RelativeTime ts={secondsNow()} /></span>);
    expect(screen.getByTestId("stamp").textContent).toBe("now");

    act(() => {
      vi.advanceTimersByTime(5 * 60000);
    });
    expect(screen.getByTestId("stamp").textContent).toBe("5m");

    act(() => {
      vi.advanceTimersByTime(60 * 60000);
    });
    expect(screen.getByTestId("stamp").textContent).toBe("1h");
  });

  it("shares one interval across every mounted stamp and clears it on the last unmount", () => {
    const spy = vi.spyOn(globalThis, "setInterval");
    const view = render(
      <>
        <RelativeTime ts={secondsNow()} />
        <RelativeTime ts={secondsNow()} />
        <RelativeTime ts={secondsNow()} />
      </>,
    );
    const ticks = spy.mock.calls.filter((c) => c[1] === TICK_MS);
    expect(ticks).toHaveLength(1);

    const clear = vi.spyOn(globalThis, "clearInterval");
    view.unmount();
    expect(clear).toHaveBeenCalled();
  });

  it("renders nothing for a missing or unparsable stamp", () => {
    const { container } = render(
      <span><RelativeTime ts={0} /><RelativeTime ts={NaN} /></span>,
    );
    expect(container.textContent).toBe("");
  });
});

describe("relativeTime", () => {
  it("accepts an injected now so a caller can drive the clock", () => {
    const ts = 1_000_000;
    expect(relativeTime(ts, ts * 1000 + 3 * 60000)).toBe("3m");
    expect(relativeTime(ts, ts * 1000)).toBe("now");
  });
});
