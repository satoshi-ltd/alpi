import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { listen } from "@tauri-apps/api/event";

import { ACCEPTANCE_TIMEOUT_MS, watchAcceptance } from "./chat-acceptance.js";

let emit;
let unlisten;

beforeEach(() => {
  vi.useFakeTimers();
  unlisten = vi.fn();
  listen.mockReset();
  listen.mockImplementation(async (_name, callback) => {
    emit = callback;
    return unlisten;
  });
});

afterEach(() => {
  vi.useRealTimers();
});

const frame = (payload) => emit({ payload });

describe("watchAcceptance", () => {
  it("accepts when the daemon starts the turn", async () => {
    const watch = watchAcceptance("r1");
    await watch.ready;
    frame({ request_id: "r1", kind: "session_start", session_id: "s1" });
    expect(await watch.promise).toEqual({ accepted: true });
    expect(unlisten).toHaveBeenCalled();
  });

  it("rejects, with the daemon's words, when an error arrives before the turn starts", async () => {
    const watch = watchAcceptance("r1");
    await watch.ready;
    frame({ request_id: "r1", kind: "error", text: "session already has a running turn" });
    frame({ request_id: "r1", kind: "reply", text: "" });
    expect(await watch.promise).toEqual({ accepted: false, text: "session already has a running turn" });
  });

  it("ignores other requests and keepalives", async () => {
    const watch = watchAcceptance("r1");
    await watch.ready;
    frame({ request_id: "r2", kind: "error", text: "not ours" });
    frame({ request_id: "r1", kind: "heartbeat" });
    frame({ request_id: "r1", kind: "session_start", session_id: "s1" });
    expect(await watch.promise).toEqual({ accepted: true });
  });

  it("gives up waiting after the timeout and treats a silent daemon as accepting", async () => {
    const watch = watchAcceptance("r1");
    await watch.ready;
    vi.advanceTimersByTime(ACCEPTANCE_TIMEOUT_MS + 1);
    expect(await watch.promise).toEqual({ accepted: true });
  });

  it("stops listening when cancelled and when the listener could not be installed", async () => {
    const watch = watchAcceptance("r1");
    await watch.ready;
    watch.cancel();
    expect(await watch.promise).toEqual({ accepted: true });
    expect(unlisten).toHaveBeenCalled();
    listen.mockRejectedValueOnce(new Error("no bridge"));
    const broken = watchAcceptance("r2");
    await broken.ready;
    expect(await broken.promise).toEqual({ accepted: true });
  });
});
