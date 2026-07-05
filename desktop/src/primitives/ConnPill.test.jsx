import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import ConnPill from "./ConnPill.jsx";

describe("ConnPill", () => {
  it("shows the host caption when online", () => {
    render(
      <ConnPill kind="remote" name="office" host="1.2.3.4:7423" status="online" />,
    );
    expect(screen.getByText("1.2.3.4:7423")).toBeInTheDocument();
  });

  it("swaps the caption for connecting… while probing", () => {
    render(
      <ConnPill kind="remote" name="office" host="1.2.3.4:7423" status="probing" />,
    );
    expect(screen.getByText("connecting…")).toBeInTheDocument();
    expect(screen.queryByText("1.2.3.4:7423")).not.toBeInTheDocument();
  });

  it("keeps the offline caption when offline", () => {
    render(<ConnPill kind="remote" name="office" host="1.2.3.4:7423" status="offline" />);
    expect(screen.getByText("offline · retrying…")).toBeInTheDocument();
  });
});
