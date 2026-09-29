import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import LoadFailed from "./LoadFailed.jsx";

describe("LoadFailed", () => {
  it("names what failed, shows the reason and retries", () => {
    const onRetry = vi.fn();
    render(<LoadFailed label="this conversation" error="read timeout" onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't load this conversation");
    expect(screen.getByText("read timeout")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("fits in a row as an inline alert", () => {
    render(<LoadFailed inline label="members" onRetry={() => {}} />);
    expect(screen.getByRole("alert").tagName).toBe("SPAN");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
