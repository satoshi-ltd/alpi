import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));

import Markdown from "./Markdown.jsx";

const BLOCK = "```chart\n" + JSON.stringify({ type: "line", x: ["Mon", "Tue", "Wed"], series: [{ name: "Chats", values: [3, 1, 4] }] }) + "\n```";

describe("Markdown — chart blocks", () => {
  it("draws a chart and hands it the speaker's accent", () => {
    const { container } = render(<Markdown source={`Trend.\n\n${BLOCK}`} className="alpi-md" accent="#8a5a0a" />);
    expect(container.querySelector("figure.md-chart svg polyline")).toBeTruthy();
    expect(container.firstChild.style.getPropertyValue("--chart-accent")).toBe("#8a5a0a");
  });

  it("falls back to the ink without an accent", () => {
    const { container } = render(<Markdown source={BLOCK} className="alpi-md" />);
    expect(container.firstChild.style.getPropertyValue("--chart-accent")).toBe("");
    expect(container.querySelector("figure.md-chart")).toBeTruthy();
  });
});
