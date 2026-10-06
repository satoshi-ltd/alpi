import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import TasksButton from "./TasksButton.jsx";

const CSS = readFileSync(join(import.meta.dirname, "TasksButton.module.css"), "utf8");
const HUB = "hub-pubkey";
const THREAD = [{ seq: 1, from_pubkey: HUB, body: "#task #qa Review launch" }];

function ruleBody(selector) {
  const escaped = selector.replace(/[.[\]"():]/g, "\\$&");
  const match = CSS.match(new RegExp(`(?:^|\\n)${escaped}\\s*\\{([^}]*)\\}`));
  return match ? match[1] : "";
}

describe("TasksButton trigger sheet", () => {
  it("rests on the hover tone with 4 px corners", () => {
    const body = ruleBody(".root .trigger");
    expect(body).toMatch(/background:\s*var\(--hover\)/);
    expect(body).toMatch(/border-radius:\s*var\(--r-xs\)/);
  });

  it("steps to the selected tone on hover and while open", () => {
    expect(CSS).toMatch(
      /\.root \.trigger:not\(:disabled\):hover,\s*\n\.root \.trigger\[aria-expanded="true"\]\s*\{\s*background:\s*var\(--selected\)/,
    );
  });

  it("marks the trigger expanded while its popover is open", () => {
    render(<TasksButton thread={THREAD} hubPubkey={HUB} openTick={0} />);
    const trigger = screen.getByText("Review launch").closest("button");
    expect(trigger.className).toContain("trigger");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
  });

  it("draws no ring while open, keeping the keyboard focus ring", () => {
    expect(ruleBody('.root .trigger[aria-expanded="true"]:not(:focus-visible)')).toMatch(/outline:\s*0/);
  });

  it("the phase form shares the sheet and expands with its menu", () => {
    const phase = { chip: null, worker: null, count: "4 of 8", line: null, idle: "idle" };
    render(<TasksButton thread={[]} hubPubkey={HUB} openTick={0} phase={phase} />);
    const trigger = screen.getByText("4 of 8").closest("button");
    expect(trigger.className).toContain("trigger");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
  });
});
