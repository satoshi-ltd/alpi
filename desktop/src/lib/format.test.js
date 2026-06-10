import { describe, it, expect } from "vitest";
import { fmtTok, formatCostLine, formatUsd } from "./format.js";

describe("format helpers", () => {
  it("fmtTok tiers K and M with one decimal until 3 digits", () => {
    expect(fmtTok(999)).toBe("999");
    expect(fmtTok(1_500)).toBe("1.5K");
    expect(fmtTok(200_000)).toBe("200K");
    expect(fmtTok(1_234_567)).toBe("1.2M");
    expect(fmtTok(null)).toBe("0");
  });

  it("formatUsd always shows two decimals", () => {
    expect(formatUsd(0.466)).toBe("$0.47");
    expect(formatUsd()).toBe("$0.00");
  });

  it("formatCostLine keeps 4 decimals under a cent", () => {
    expect(formatCostLine({ tokens: 1500, usd: 0.36 })).toBe("1.5K · $0.36");
    expect(formatCostLine({ tokens: 200, usd: 0.0042 })).toBe("200 · $0.0042");
    expect(formatCostLine(null)).toBe("0 · $0.0000");
  });
});
