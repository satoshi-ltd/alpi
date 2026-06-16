import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
import { useRenderedMarkdown } from "./markdownImages.js";

const SRC = "![x](/tmp/markdown-images-retry.png)";

beforeEach(() => {
  invoke.mockReset();
  invoke.mockResolvedValue(null);
});

describe("useRenderedMarkdown thumb cache", () => {
  it("retries a failed thumb on remount instead of caching the failure", async () => {
    invoke.mockRejectedValueOnce(new Error("transient"));
    const first = renderHook(() => useRenderedMarkdown(SRC));
    await waitFor(() => expect(invoke).toHaveBeenCalledTimes(1));
    expect(first.result.current).toContain('data-src="/tmp/markdown-images-retry.png"');
    expect(first.result.current).not.toContain('src="data:');
    first.unmount();

    invoke.mockResolvedValueOnce("data:image/png;base64,AAAA");
    const second = renderHook(() => useRenderedMarkdown(SRC));
    await waitFor(() =>
      expect(second.result.current).toContain('src="data:image/png;base64,AAAA"'),
    );
  });
});
