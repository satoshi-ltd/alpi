import { describe, expect, it } from "vitest";
import {
  pairingDisplayStatus,
  pairingExpiryText,
  pairingSecondsRemaining,
} from "./pairing-expiry.js";

describe("pairing expiry", () => {
  const now = 1_800_000_000_000;

  it("formats the daemon deadline as a live countdown", () => {
    expect(pairingSecondsRemaining(1_800_000_061, now)).toBe(61);
    expect(pairingExpiryText(1_800_000_061, "pending", now)).toBe("expires in 1m 1s");
    expect(pairingExpiryText(1_800_000_059, "pending", now)).toBe("expires in 59s");
  });

  it("marks a pending code expired as soon as its deadline passes", () => {
    expect(pairingDisplayStatus("pending", 1_800_000_000, now)).toBe("expired");
    expect(pairingExpiryText(1_800_000_000, "pending", now)).toBe("expired just now");
    expect(pairingExpiryText(1_800_000_000, "expired", now + 120_000))
      .toBe("expired 2m ago");
  });

  it("keeps terminal daemon states instead of showing a countdown", () => {
    expect(pairingExpiryText(1_800_000_061, "consumed", now)).toBe("consumed");
    expect(pairingExpiryText(1_800_000_061, "cancelled", now)).toBe("cancelled");
  });
});
