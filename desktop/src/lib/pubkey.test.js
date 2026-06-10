import { describe, it, expect } from "vitest";
import { pubkeyTail, shortPubkey } from "./pubkey.js";

describe("pubkey display helpers", () => {
  it("shortPubkey defaults to 16 chars with ellipsis and tolerates null", () => {
    expect(shortPubkey("abcdefghijklmnopqrstuv")).toBe("abcdefghijklmnop…");
    expect(shortPubkey("abcdefghijklmnopqrstuv", 12)).toBe("abcdefghijkl…");
    expect(shortPubkey(null)).toBe("…");
  });

  it("pubkeyTail keeps the last 7 chars", () => {
    expect(pubkeyTail("abcdefghijklmnop")).toBe("…jklmnop");
    expect(pubkeyTail(null)).toBe("…");
  });
});
