import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { useDelayedFlag } from "./useDelayedFlag.js";

function Harness({ active }) {
  const on = useDelayedFlag(active, 450);
  return <div data-testid="flag">{on ? "on" : "off"}</div>;
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("useDelayedFlag", () => {
  it("stays off until the delay elapses, then turns on", () => {
    render(<Harness active />);
    expect(screen.getByTestId("flag").textContent).toBe("off");
    act(() => vi.advanceTimersByTime(450));
    expect(screen.getByTestId("flag").textContent).toBe("on");
  });

  it("never turns on when the flag drops before the delay", () => {
    const { rerender } = render(<Harness active />);
    act(() => vi.advanceTimersByTime(300));
    rerender(<Harness active={false} />);
    act(() => vi.advanceTimersByTime(1000));
    expect(screen.getByTestId("flag").textContent).toBe("off");
  });

  it("turns off immediately when the flag drops", () => {
    const { rerender } = render(<Harness active />);
    act(() => vi.advanceTimersByTime(450));
    expect(screen.getByTestId("flag").textContent).toBe("on");
    rerender(<Harness active={false} />);
    expect(screen.getByTestId("flag").textContent).toBe("off");
  });
});
