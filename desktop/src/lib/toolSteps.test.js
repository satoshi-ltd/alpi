import { describe, expect, it } from "vitest";

import { fmtToolDuration, prettyArgs, toolIcon, toolResult, toolSummary } from "./toolSteps.js";

describe("toolIcon", () => {
  it("maps each family to its glyph and memory to its own", () => {
    expect(toolIcon("read_file")).toBe("file");
    expect(toolIcon("list_dir")).toBe("file");
    expect(toolIcon("terminal")).toBe("terminal");
    expect(toolIcon("web_search")).toBe("globe");
    expect(toolIcon("grep")).toBe("search");
    expect(toolIcon("peer")).toBe("link");
    expect(toolIcon("send_message")).toBe("link");
    expect(toolIcon("memory")).toBe("brain");
    expect(toolIcon("todo")).toBe("cpu");
  });
});

describe("toolSummary", () => {
  it("uses the daemon's plain preview when the frame carried one", () => {
    expect(toolSummary({ preview: "deploy.log", args: { path: "/var/log/deploy.log" } })).toBe("deploy.log");
  });

  it("falls back to the primary argument for stored calls", () => {
    expect(toolSummary({ args: { command: "npm run lint", timeout: 30 } })).toBe("npm run lint");
    expect(toolSummary({ args: { action: "add", target: "user" } })).toBe("add · user");
  });

  it("keeps the old key=value hint for unknown shapes", () => {
    expect(toolSummary({ args: { a: 1, b: [2] } })).toBe("a=1 b=[2]");
  });
});

describe("fmtToolDuration", () => {
  it("shows tenths under ten seconds and whole units above", () => {
    expect(fmtToolDuration(0.24)).toBe("0.2s");
    expect(fmtToolDuration(4.06)).toBe("4.1s");
    expect(fmtToolDuration(12.4)).toBe("12s");
    expect(fmtToolDuration(65)).toBe("1m 5s");
    expect(fmtToolDuration(undefined)).toBe("");
  });
});

describe("prettyArgs", () => {
  it("pretty-prints objects and JSON strings", () => {
    expect(prettyArgs({ a: 1 })).toBe('{\n  "a": 1\n}');
    expect(prettyArgs('{"a":1}')).toBe('{\n  "a": 1\n}');
    expect(prettyArgs("not json")).toBe("not json");
  });
});

describe("toolResult", () => {
  it("flags a capped stored result as an excerpt", () => {
    const stored = `${"x".repeat(399)}…`;
    expect(toolResult({ result: stored })).toEqual({ text: stored, excerpt: true });
    expect(toolResult({ result: "short" })).toEqual({ text: "short", excerpt: false });
  });

  it("prefers live output and only calls it an excerpt past the live cap", () => {
    expect(toolResult({ output: "live", result: "stored" })).toEqual({ text: "live", excerpt: false });
    const live = `${"y".repeat(3999)}…`;
    expect(toolResult({ output: live }).excerpt).toBe(true);
    expect(toolResult({ output: `${"z".repeat(399)}…` }).excerpt).toBe(false);
  });

  it("is empty when nothing came back", () => {
    expect(toolResult({})).toBeNull();
  });
});
