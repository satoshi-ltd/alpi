import { getConfig } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

describe("test setup", () => {
  it("lets findBy and waitFor outlast a loaded full run", () => {
    expect(getConfig().asyncUtilTimeout).toBeGreaterThanOrEqual(10000);
  });

  it("gives a whole test room for several of those waits on a slow runner", () => {
    const config = readFileSync(join(import.meta.dirname, "..", "..", "vitest.config.js"), "utf8");
    const seconds = (key) => Number(config.match(new RegExp(`${key}:\\s*(\\d+)`))[1]);
    expect(seconds("testTimeout")).toBeGreaterThanOrEqual(15000);
    expect(seconds("hookTimeout")).toBeGreaterThanOrEqual(15000);
  });
});
