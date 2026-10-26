import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import ConnPill from "./ConnPill.jsx";

describe("ConnPill", () => {
  it("shows only the host when online, because the dot already says online", () => {
    render(
      <ConnPill kind="remote" name="office" host="1.2.3.4:7423" status="online" />,
    );
    expect(screen.getByText("1.2.3.4:7423")).toBeInTheDocument();
    expect(screen.queryByText(/online/)).toBeNull();
  });

  it("still names the state for assistive technology", () => {
    render(<ConnPill kind="local" name="this device" status="online" />);
    expect(screen.getByRole("button", { name: "this device, online" })).toBeInTheDocument();
  });

  it("includes the visible host in the accessible name", () => {
    render(<ConnPill kind="remote" name="office" host="1.2.3.4:7423" status="online" />);
    expect(screen.getByRole("button", { name: "office, online, 1.2.3.4:7423" })).toBeInTheDocument();
  });

  it("does not pulse the dot while offline", () => {
    const { container } = render(<ConnPill kind="remote" name="office" host="h" status="offline" />);
    expect(container.querySelector(".pulse-dot")).toBeNull();
  });

  it("still pulses the dot while connecting", () => {
    const { container } = render(<ConnPill kind="remote" name="office" host="h" status="probing" />);
    expect(container.querySelector(".pulse-dot")).not.toBeNull();
  });

  it("swaps the caption for connecting… while probing", () => {
    render(
      <ConnPill kind="remote" name="office" host="1.2.3.4:7423" status="probing" />,
    );
    expect(screen.getByText("connecting…")).toBeInTheDocument();
    expect(screen.queryByText("1.2.3.4:7423")).not.toBeInTheDocument();
  });

  it("names the temporary throttle without offering a re-pair", () => {
    render(<ConnPill kind="remote" name="office" host="1.2.3.4:7423" status="rate-limited" />);
    expect(screen.getByText("rate limited · retrying in a minute")).toBeInTheDocument();
    expect(screen.queryByText("offline")).not.toBeInTheDocument();
  });

  it("keeps one quiet offline word when offline", () => {
    render(<ConnPill kind="remote" name="office" host="1.2.3.4:7423" status="offline" />);
    expect(screen.getByText("offline")).toBeInTheDocument();
  });

  it("shows a stable disabled state without retry copy", () => {
    render(<ConnPill kind="remote" name="office" host="1.2.3.4:7423" status="disabled" />);
    expect(screen.getByText("disabled")).toBeInTheDocument();
    expect(screen.queryByText("offline")).not.toBeInTheDocument();
  });
});
