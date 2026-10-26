import { getConfig } from "@testing-library/react";
import { describe, expect, it } from "vitest";

describe("test setup", () => {
  it("lets findBy and waitFor outlast a loaded full run", () => {
    expect(getConfig().asyncUtilTimeout).toBeGreaterThanOrEqual(5000);
  });
});
