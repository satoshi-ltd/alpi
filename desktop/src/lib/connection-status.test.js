import { describe, it, expect } from "vitest";

import {
  RATE_LIMITED_MESSAGE,
  describeConnectionError,
  isRateLimitedError,
} from "./connection-status.js";

describe("connection-status", () => {
  it("recognises only the daemon's rate-limit close, not any 1013", () => {
    expect(isRateLimitedError("websocket closed by daemon (1013 auth-rate-limited)")).toBe(true);
    expect(isRateLimitedError("websocket closed by daemon (1013 Device connection limit reached)")).toBe(false);
    expect(isRateLimitedError("alp -32000: auth-failed")).toBe(false);
    expect(isRateLimitedError(null)).toBe(false);
  });

  it("describes the throttle for people and passes other errors through", () => {
    expect(describeConnectionError("websocket closed by daemon (1013 auth-rate-limited)")).toBe(RATE_LIMITED_MESSAGE);
    expect(describeConnectionError("model timeout")).toBe("model timeout");
  });
});
