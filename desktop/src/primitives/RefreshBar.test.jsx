import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import RefreshBar from "./RefreshBar.jsx";

describe("RefreshBar", () => {
  it("stays visible while a controlled fetch is active", () => {
    const { rerender } = render(
      <RefreshBar active controlled label="Fetching latest settings" />,
    );
    expect(screen.getByRole("progressbar", { name: "Fetching latest settings" }))
      .toBeInTheDocument();

    rerender(
      <RefreshBar active={false} controlled label="Fetching latest settings" />,
    );
    expect(screen.queryByRole("progressbar")).toBeNull();
  });
});
