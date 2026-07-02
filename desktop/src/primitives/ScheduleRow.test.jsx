import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { ScheduleRow } from "./SettingsLayout.jsx";

const base = {
  id: "abc123", cron: "0 2 * * 4",
  title: "Sports this weekend",
  prompt: "python3 ${ALPI_HOME}/skills/personal/sports-weekend/scripts/run.py",
  on: true,
};
const noop = () => {};

describe("ScheduleRow", () => {
  it("shows the title and the cron expression (no 'cron' word)", () => {
    render(
      <ScheduleRow
        s={{ ...base, noAgent: true, notify: true }}
        onFire={noop} onToggle={noop} onDelete={noop}
      />,
    );
    expect(screen.getByText("Sports this weekend")).toBeTruthy();
    expect(screen.getByText("0 2 * * 4")).toBeTruthy();
  });

  it("falls back to the prompt when there is no title", () => {
    render(
      <ScheduleRow
        s={{ ...base, title: "", noAgent: true, notify: false }}
        onFire={noop} onToggle={noop} onDelete={noop}
      />,
    );
    expect(screen.getByText(base.prompt)).toBeTruthy();
  });

  it("fires and toggles via the icon buttons", () => {
    const onFire = vi.fn();
    const onToggle = vi.fn();
    render(
      <ScheduleRow
        s={{ ...base, noAgent: true, notify: true, on: true }}
        onFire={onFire} onToggle={onToggle} onDelete={noop}
      />,
    );
    fireEvent.click(screen.getByLabelText("Run now"));
    fireEvent.click(screen.getByLabelText("Disable"));
    expect(onFire).toHaveBeenCalledTimes(1);
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("shows Enable when the job is paused", () => {
    render(
      <ScheduleRow
        s={{ ...base, noAgent: false, notify: false, on: false }}
        onFire={noop} onToggle={noop} onDelete={noop}
      />,
    );
    expect(screen.getByLabelText("Enable")).toBeTruthy();
  });

  it("carries the last-run as a tooltip on the cron chip", () => {
    render(
      <ScheduleRow
        s={{ ...base, lastRun: "ran 2h ago" }}
        onFire={noop} onToggle={noop} onDelete={noop}
      />,
    );
    const tip = screen.getByText("0 2 * * 4").closest(".ds-tip");
    expect(tip).toBeTruthy();
    expect(tip.textContent).toContain("ran 2h ago");
  });

  it("renders no cron tooltip when last-run is absent", () => {
    render(
      <ScheduleRow s={base} onFire={noop} onToggle={noop} onDelete={noop} />,
    );
    const chip = screen.getByText("0 2 * * 4");
    expect(chip.closest(".ds-tip")).toBeNull();
  });
});
