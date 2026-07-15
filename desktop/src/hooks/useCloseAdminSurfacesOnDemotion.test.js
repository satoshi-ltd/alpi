import { describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";

import { useCloseAdminSurfacesOnDemotion } from "./useCloseAdminSurfacesOnDemotion.js";

describe("useCloseAdminSurfacesOnDemotion", () => {
  it("resets when permission drops admin→member", () => {
    const reset = vi.fn();
    const { rerender } = renderHook(
      ({ allowed }) => useCloseAdminSurfacesOnDemotion(allowed, reset),
      { initialProps: { allowed: true } },
    );
    expect(reset).not.toHaveBeenCalled();
    rerender({ allowed: false });
    expect(reset).toHaveBeenCalledTimes(1);
  });

  it("does not reset while staying admin", () => {
    const reset = vi.fn();
    const { rerender } = renderHook(
      ({ allowed }) => useCloseAdminSurfacesOnDemotion(allowed, reset),
      { initialProps: { allowed: true } },
    );
    rerender({ allowed: true });
    expect(reset).not.toHaveBeenCalled();
  });
});
