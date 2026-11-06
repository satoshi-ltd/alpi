import { describe, it, expect, beforeEach, vi } from "vitest";

const openUrl = vi.fn(() => Promise.resolve());
vi.mock("@tauri-apps/plugin-opener", () => ({ openUrl: (...args) => openUrl(...args) }));

import { installExternalLinkGuard, openExternal } from "./openExternal.js";

function anchor(href, extra = {}) {
  const a = document.createElement("a");
  a.setAttribute("href", href);
  Object.entries(extra).forEach(([k, v]) => a.setAttribute(k, v));
  a.textContent = href;
  document.body.appendChild(a);
  return a;
}

function click(el) {
  const event = new MouseEvent("click", { bubbles: true, cancelable: true });
  el.dispatchEvent(event);
  return event.defaultPrevented;
}

beforeEach(() => {
  openUrl.mockClear();
  document.body.innerHTML = "";
});

describe("openExternal", () => {
  it("opens http, https and mailto through the opener and refuses every other scheme", async () => {
    expect(await openExternal("https://example.com/x")).toBe(true);
    expect(await openExternal("mailto:a@b.c")).toBe(true);
    expect(await openExternal("javascript:alert(1)")).toBe(false);
    expect(await openExternal("file:///etc/passwd")).toBe(false);
    expect(await openExternal("data:text/html,hi")).toBe(false);
    expect(openUrl.mock.calls.map((c) => c[0])).toEqual(["https://example.com/x", "mailto:a@b.c"]);
  });
});

describe("installExternalLinkGuard", () => {
  it("sends external anchors to the opener, leaves internal and self-handled ones alone", () => {
    const stop = installExternalLinkGuard(document);
    expect(click(anchor("https://example.com/a"))).toBe(true);
    expect(click(anchor("#section"))).toBe(false);
    expect(click(anchor("javascript:alert(1)"))).toBe(false);
    expect(click(anchor("https://example.com/b", { "data-external-handled": "" }))).toBe(false);
    expect(openUrl.mock.calls.map((c) => c[0])).toEqual(["https://example.com/a"]);
    stop();
    expect(click(anchor("https://example.com/c"))).toBe(false);
    expect(openUrl).toHaveBeenCalledTimes(1);
  });
});
