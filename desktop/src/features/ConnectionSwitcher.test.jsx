import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";

import { useFireOnce } from "./ConnectionSwitcher.jsx";

describe("useFireOnce", () => {
  it("fires the callback the first time signal becomes truthy", () => {
    const cb = vi.fn();
    const { rerender } = renderHook(({ signal }) => useFireOnce(signal, cb), {
      initialProps: { signal: false },
    });
    expect(cb).not.toHaveBeenCalled();
    rerender({ signal: true });
    expect(cb).toHaveBeenCalledTimes(1);
  });

  it("does not re-fire on a second false→true transition (once-per-session)", () => {
    const cb = vi.fn();
    const { rerender } = renderHook(({ signal }) => useFireOnce(signal, cb), {
      initialProps: { signal: true },
    });
    expect(cb).toHaveBeenCalledTimes(1);
    rerender({ signal: false });
    rerender({ signal: true });
    expect(cb).toHaveBeenCalledTimes(1);
  });

  it("does not fire when signal is never truthy", () => {
    const cb = vi.fn();
    const { rerender } = renderHook(({ signal }) => useFireOnce(signal, cb), {
      initialProps: { signal: false },
    });
    rerender({ signal: false });
    expect(cb).not.toHaveBeenCalled();
  });
});
